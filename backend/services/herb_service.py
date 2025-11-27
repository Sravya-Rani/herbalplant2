import base64
import logging
import os
import mimetypes
import re
import time
from pathlib import Path
from threading import Lock
from typing import Dict, Optional
from urllib.parse import quote

import httpx

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    load_dotenv = None

logger = logging.getLogger(__name__)

# Import database service
try:
    from services.db_service import get_herb_by_name, get_herb_by_scientific_name
    from database.models import get_db, Herb
except ImportError:
    logger.warning("Database services not available. Medical uses lookup will be limited.")
    get_herb_by_name = None
    get_herb_by_scientific_name = None
    get_db = None
    Herb = None

if load_dotenv:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

PLANT_ID_API_URL = os.getenv("PLANT_ID_API_URL", "https://plant.id/api/v3/identification")
PLANT_ID_API_KEY_ENV = "PLANT_ID_API_KEY"

# PlantNet configuration
PLANTNET_API_URL = os.getenv(
    "PLANTNET_API_URL",
    "https://my-api.plantnet.org/v2/identify/all",
)
PLANTNET_API_KEY_ENV = "PLANTNET_API_KEY"

# Provider selection: "plantid" (default) or "plantnet"
PLANT_PROVIDER = (os.getenv("PLANT_PROVIDER") or "plantid").lower()

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HERB_EXCEL_PATH = Path(
    os.getenv("HERB_EXCEL_PATH") or _DEFAULT_DATA_DIR / "herb_uses.xlsx"
)

_excel_cache: Optional[Dict[str, str]] = None
_excel_cache_mtime: Optional[float] = None
_excel_cache_lock = Lock()

_EXCEL_NAME_CANDIDATES = [
    "common name",
    "common_name",
    "common names",
    "herb name",
    "name",
]
_EXCEL_USE_CANDIDATES = [
    "uses",
    "use",
    "medical uses",
    "medicinal use",
    "benefits",
]

_DEFAULT_FAILURE_RESPONSE: Dict[str, str] = {
    "common_name": "Unknown herb",
    "scientific_name": "N/A",
    "uses": "We could not identify this plant. Please try another, clearer photo.",
}


def _build_failure_response(message: str) -> Dict[str, str]:
    """Return a formatted error response that matches the HerbResponse schema."""
    failure = dict(_DEFAULT_FAILURE_RESPONSE)
    failure["uses"] = message
    return failure


def _normalize_common_name(name: str) -> str:
    """Normalize common names for consistent Excel lookups."""
    if not name:
        return ""
    cleaned = name.strip().lower()
    if "(" in cleaned:
        cleaned = cleaned.split("(")[0].strip()
    return re.sub(r"[^a-z0-9]+", "", cleaned)


def _split_aliases(cell_value: object) -> list[str]:
    """Split a cell containing multiple aliases into individual names."""
    if cell_value is None:
        return []
    if isinstance(cell_value, float) and str(cell_value) == "nan":
        return []
    value = str(cell_value).strip()
    if not value:
        return []
    tokens = re.split(r"[;,/|\n]+", value)
    return [token.strip() for token in tokens if token.strip()]


def _resolve_excel_column(columns, candidates) -> Optional[str]:
    """Find the real column name matching one of the candidate headers."""
    normalized = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in normalized:
            return normalized[key]
    return None


def _load_excel_cache() -> Optional[Dict[str, str]]:
    """Load and cache Excel data to avoid repeated disk reads."""
    if not pd:
        logger.debug("pandas is not installed; skipping Excel-based lookup.")
        return None
    path = HERB_EXCEL_PATH
    if not path or not path.exists():
        logger.debug("Herb Excel file not found at %s", path)
        return None

    try:
        current_mtime = path.stat().st_mtime
    except OSError as exc:
        logger.error("Unable to read Excel file metadata: %s", exc)
        return None

    global _excel_cache, _excel_cache_mtime
    with _excel_cache_lock:
        if _excel_cache is not None and _excel_cache_mtime == current_mtime:
            return _excel_cache

        try:
            df = pd.read_excel(path)
        except Exception as exc:  # pragma: no cover - depends on local file
            logger.error("Failed to load herb Excel file %s: %s", path, exc)
            return None

        name_col = _resolve_excel_column(df.columns, _EXCEL_NAME_CANDIDATES)
        uses_col = _resolve_excel_column(df.columns, _EXCEL_USE_CANDIDATES)

        if not name_col or not uses_col:
            logger.warning(
                "Excel file %s is missing expected columns. "
                "Found columns: %s",
                path,
                list(df.columns),
            )
            return None

        mapping: Dict[str, str] = {}
        for _, row in df.iterrows():
            aliases = _split_aliases(row.get(name_col))
            if not aliases:
                continue
            uses_value = row.get(uses_col)
            if uses_value is None:
                continue
            uses_text = str(uses_value).strip()
            if not uses_text:
                continue

            for alias in aliases:
                normalized = _normalize_common_name(alias)
                if not normalized:
                    continue
                mapping[normalized] = uses_text

        _excel_cache = mapping or None
        _excel_cache_mtime = current_mtime
        return _excel_cache


def _get_uses_from_excel(common_name: str) -> Optional[str]:
    """Retrieve uses from the Excel sheet by matching the common name."""
    if not common_name:
        return None

    cache = _load_excel_cache()
    if not cache:
        return None

    possible_names = [common_name]
    if " (" in common_name:
        possible_names.append(common_name.split("(")[0])
    if " " in common_name:
        possible_names.append(common_name.split()[0])

    normalized_variants = [
        _normalize_common_name(name) for name in possible_names if name
    ]

    seen = set()
    for variant in normalized_variants:
        if not variant or variant in seen:
            continue
        seen.add(variant)
        if variant in cache:
            logger.info("Matched uses for %s via Excel file", common_name)
            return cache[variant]

    # Fuzzy fallback – check containment
    for variant in seen:
        for key, value in cache.items():
            if variant and variant in key:
                logger.info("Fuzzy Excel match %s -> %s", common_name, key)
                return value

    return None


def _get_medical_uses_from_db(common_name: str, scientific_name: str) -> Optional[str]:
    """Get medical uses from the database by common name or scientific name.
    
    Returns the uses string if found, None otherwise.
    """
    if not get_db or not get_herb_by_name or not get_herb_by_scientific_name:
        logger.warning("Database services not available for medical uses lookup")
        return None
    
    db = None
    try:
        db = next(get_db())
        
        # Check if database has any herbs
        if Herb:
            total_herbs = db.query(Herb).count()
            logger.debug("Database contains %d herbs", total_herbs)
            if total_herbs == 0:
                logger.warning("Database is empty. Run init_database.py to populate it.")
                return None
        
        # Try to find by scientific name first (more accurate)
        if scientific_name and scientific_name != "Unknown":
            logger.debug("Searching database for scientific name: %s", scientific_name)
            herb = get_herb_by_scientific_name(db, scientific_name)
            if herb and herb.uses:
                logger.info("Found medical uses in database for scientific name: %s", scientific_name)
                return herb.uses
            else:
                logger.debug("No match found for scientific name: %s", scientific_name)
        
        # Try to find by common name
        if common_name and common_name != "Unknown herb":
            logger.debug("Searching database for common name: %s", common_name)
            
            # Try exact/partial match first (db_service uses ilike with %name%)
            herb = get_herb_by_name(db, common_name)
            if herb and herb.uses:
                logger.info("Found medical uses in database for common name: %s", common_name)
                return herb.uses
            
            # Try partial match - get the first word (e.g., "Neem tree" -> "Neem")
            clean_name = common_name.split()[0] if " " in common_name else common_name
            # Also try without parentheses (e.g., "Tulsi (Holy Basil)" -> "Tulsi")
            if "(" in clean_name:
                clean_name = clean_name.split("(")[0].strip()
            
            if clean_name != common_name:
                logger.debug("Trying cleaned name: %s", clean_name)
                herb = get_herb_by_name(db, clean_name)
                if herb and herb.uses:
                    logger.info("Found medical uses in database for cleaned name: %s", clean_name)
                    return herb.uses
            
            # Try case-insensitive direct lookup in database
            if Herb:
                all_herbs = db.query(Herb).all()
                logger.debug("Checking %d herbs for fuzzy match with: %s", len(all_herbs), clean_name)
                for h in all_herbs:
                    if h.common_name and clean_name.lower() in h.common_name.lower():
                        if h.uses:
                            logger.info("Found medical uses in database via fuzzy match: %s -> %s", clean_name, h.common_name)
                            return h.uses
                    # Also check if the database name is in the search name
                    if h.common_name and h.common_name.lower() in clean_name.lower():
                        if h.uses:
                            logger.info("Found medical uses in database via reverse fuzzy match: %s -> %s", clean_name, h.common_name)
                            return h.uses
        
        logger.debug("No medical uses found in database for: common_name=%s, scientific_name=%s", common_name, scientific_name)
        return None
    except Exception as exc:
        logger.error("Error querying database for medical uses: %s", exc, exc_info=True)
        return None
    finally:
        # Ensure database session is closed
        if db:
            try:
                db.close()
            except:
                pass


def _fetch_wikipedia_summary(query: str) -> Optional[str]:
    """Fetch usage information from Wikipedia for the given query.
    
    Returns a summary focusing on uses, medicinal properties, and traditional applications.
    """
    if not query:
        return None

    # Clean and format the query for Wikipedia URL
    title = query.strip().replace(" ", "_")
    title = quote(title, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

    try:
        response = httpx.get(
            url,
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )
    except httpx.HTTPError as exc:
        logger.debug("Wikipedia summary lookup failed for %s: %s", query, exc)
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
        extract = data.get("extract", "")
        
        if extract:
            import re
            # Extract sentences that mention uses
            sentences = re.split(r'[.!?]+', extract)
            usage_sentences = []
            
            usage_keywords = [
                "used to", "used for", "treat", "treatment", "medicinal", "medicine",
                "herb", "traditional", "benefit", "cure", "heal", "therapeutic",
                "application", "property", "helps", "effective", "remedy", "reduces", "prevents"
            ]
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                sentence_lower = sentence.lower()
                if any(keyword in sentence_lower for keyword in usage_keywords):
                    usage_sentences.append(sentence)
            
            if usage_sentences:
                # Combine relevant sentences about uses
                result = '. '.join(usage_sentences[:4])  # Take up to 4 relevant sentences
                return result + "." if not result.endswith('.') else result
            
            # If no usage sentences found but extract exists, return it if substantial
            if len(extract) > 100:
                return extract[:500] + "..." if len(extract) > 500 else extract
    except (KeyError, ValueError) as exc:
        logger.debug("Error parsing Wikipedia response for %s: %s", query, exc)
        return None

    return None


def _get_best_available_uses(common_name: str, scientific_name: str) -> Optional[str]:
    """Aggregate lookup strategy prioritizing Excel, then DB, then Wikipedia."""
    uses = _get_uses_from_excel(common_name)
    if uses:
        return uses

    uses = _get_medical_uses_from_db(common_name, scientific_name)
    if uses:
        return uses

    if scientific_name and scientific_name not in {"Unknown", "N/A"}:
        uses = _fetch_wikipedia_summary(scientific_name)
        if uses:
            return uses

    if common_name and common_name not in {"Unknown", "Unknown herb"}:
        uses = _fetch_wikipedia_summary(common_name)
        if uses:
            return uses

    return None


def _identify_with_plantid(image_path: str) -> Dict[str, str]:
    """Identify herb using the Plant.id provider."""
    api_key = os.getenv(PLANT_ID_API_KEY_ENV)

    if not api_key:
        logger.error("Plant.id API key missing. Set %s in the backend environment.", PLANT_ID_API_KEY_ENV)
        return _build_failure_response(
            "Plant identification service is not configured. Please contact the administrator."
        )

    try:
        with open(image_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    except OSError as exc:
        logger.exception("Unable to read uploaded image for identification: %s", exc)
        return _build_failure_response("Unable to read the uploaded image. Please try again.")

    payload: Dict[str, object] = {
        "images": [image_base64],
        "plant_language": "en",
        "plant_details": [
            "common_names",
            "name_authority",
            "wiki_description",
            "taxonomy",
            "url",
        ],
    }

    headers = {
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            PLANT_ID_API_URL,
            json=payload,
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        )
    except httpx.TimeoutException:
        logger.warning("Plant.id API request timed out.")
        return _build_failure_response("The identification service timed out. Please try again with a clearer photo.")
    except httpx.HTTPError as exc:
        logger.exception("Plant.id API request failed: %s", exc)
        return _build_failure_response("Failed to contact the identification service. Please try again later.")

    if response.status_code not in (200, 201):
        logger.error("Plant.id API error %s: %s", response.status_code, response.text)
        return _build_failure_response(
            f"Identification service returned an error ({response.status_code}). Please try again later."
        )

    data = response.json()
    suggestions = data.get("suggestions") or []

    if not suggestions:
        logger.info("Plant.id API did not return suggestions: %s", data)
        return _build_failure_response("No matching herbs were found. Try another angle or better lighting.")

    top_suggestion = suggestions[0]
    plant_details = top_suggestion.get("plant_details", {})

    common_names = plant_details.get("common_names") or []
    common_name = common_names[0] if common_names else top_suggestion.get("plant_name", "Unknown")
    scientific_name = top_suggestion.get("plant_name", "Unknown")
    
    uses = _get_best_available_uses(common_name, scientific_name)

    if not uses:
        wiki_description = plant_details.get("wiki_description") or {}
        uses = wiki_description.get("value") or "No additional information available."

    return {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "uses": uses,
    }


def _identify_with_plantnet(image_path: str) -> Dict[str, str]:
    """Identify plant using PlantNet (pl@ntnet) API.

    API docs expect multipart/form-data with one or more "images" parts
    and an "organs" field (e.g., leaf). Authentication is via api-key
    query parameter.
    """
    api_key = os.getenv(PLANTNET_API_KEY_ENV)
    if not api_key:
        logger.error("PlantNet API key missing. Set %s in the backend environment.", PLANTNET_API_KEY_ENV)
        return _build_failure_response(
            "PlantNet identification service is not configured. Please contact the administrator."
        )

    query_params = {"api-key": api_key}
    data = {"organs": "leaf"}

    try:
        with open(image_path, "rb") as f:
            # Automatically guess the content type
            content_type, _ = mimetypes.guess_type(image_path)
            if not content_type:
                content_type = "image/jpeg"  # A safe default

            files = [("images", (os.path.basename(image_path), f, content_type))]
            
            response = httpx.post(
                PLANTNET_API_URL,
                params=query_params,
                data=data,
                files=files,
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            )
    except OSError as exc:
        logger.exception("Unable to read uploaded image for PlantNet: %s", exc)
        return _build_failure_response("Unable to read the uploaded image. Please try again.")
    except httpx.TimeoutException:
        logger.warning("PlantNet API request timed out.")
        return _build_failure_response("The identification service timed out. Please try again with a clearer photo.")
    except httpx.HTTPError as exc:
        logger.exception("PlantNet API request failed: %s", exc)
        return _build_failure_response("Failed to contact the identification service. Please try again later.")

    if response.status_code not in (200, 201):
        logger.error("PlantNet API error %s: %s", response.status_code, response.text)
        return _build_failure_response(
            f"Identification service returned an error ({response.status_code}). Please try again later."
        )

    data_json = response.json()
    results = data_json.get("results") or []
    if not results:
        logger.info("PlantNet API did not return results: %s", data_json)
        return _build_failure_response("No matching herbs were found. Try another angle or better lighting.")

    top = results[0]
    # Log the structure for debugging
    logger.debug("PlantNet top result: %s", top)
    species = (top.get("species") or {})
    logger.debug("PlantNet species data: %s", species)
    scientific_name = species.get("scientificNameWithoutAuthor") or species.get("scientificName") or "Unknown"
    
    # Extract common names - try multiple possible fields
    common_names = species.get("commonNames") or []
    if not common_names:
        # Sometimes common names are in a different format
        common_names = species.get("commonName") or []
        if isinstance(common_names, str):
            common_names = [common_names]
    
    # Use first common name, or scientific name as fallback, or "Unknown herb"
    if common_names:
        common_name = common_names[0]
    elif scientific_name and scientific_name != "Unknown":
        # Use scientific name as common name if no common name available
        common_name = scientific_name.split()[0] if " " in scientific_name else scientific_name
    else:
        common_name = "Unknown herb"

    score = top.get("score")
    
    uses_description = _get_best_available_uses(common_name, scientific_name)

    if not uses_description and common_name and common_name != "Unknown herb":
        for suffix in [" herb", " plant", ""]:
            uses_description = _fetch_wikipedia_summary(f"{common_name}{suffix}")
            if uses_description:
                break

    # Final fallback message
    if not uses_description:
        uses_description = (
            f"This plant ({scientific_name}) has been identified. "
            f"Medical uses information is not available in our database. "
            f"Please consult a qualified herbalist or medical professional for usage information."
        )

    return {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "uses": uses_description,
    }


def identify_herb(image_path: str) -> Dict[str, str]:
    """Identify herb via configured provider and report elapsed time."""
    start_time = time.perf_counter()

    if PLANT_PROVIDER == "plantnet":
        result = _identify_with_plantnet(image_path)
    else:
        result = _identify_with_plantid(image_path)

    elapsed = round(time.perf_counter() - start_time, 2)
    if isinstance(result, dict):
        result["time_taken_seconds"] = elapsed
        return result

    failure = _build_failure_response("Identification failed unexpectedly.")
    failure["time_taken_seconds"] = elapsed
    return failure
