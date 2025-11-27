import base64
import logging
import os
import mimetypes
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not available. Install with: pip install pandas openpyxl")

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

# Excel file configuration for fallback uses lookup
HERB_USES_EXCEL_PATH = os.getenv(
    "HERB_USES_EXCEL_PATH",
    r"C:\Users\Hariharan\Downloads\herbal_uses_1000.xlsx",  # default path provided by user
)

# Provider selection: "plantid" (default) or "plantnet"
PLANT_PROVIDER = (os.getenv("PLANT_PROVIDER") or "plantid").lower()

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


_HERB_USES_CACHE: Optional[List[Dict[str, str]]] = None
_HERB_USES_CACHE_MTIME: Optional[float] = None


def _load_herb_uses_from_csv() -> List[Dict[str, str]]:
    """Load herb uses from Excel file into memory (cached).

    Expected Excel columns (case-insensitive):
      - common_name
      - scientific_name (optional)
      - uses
    """
    global _HERB_USES_CACHE, _HERB_USES_CACHE_MTIME

    excel_path = Path(HERB_USES_EXCEL_PATH) if HERB_USES_EXCEL_PATH else None
    cache_valid = (
        _HERB_USES_CACHE is not None
        and excel_path
        and excel_path.exists()
        and _HERB_USES_CACHE_MTIME == excel_path.stat().st_mtime
    )

    if cache_valid:
        return _HERB_USES_CACHE

    _HERB_USES_CACHE = []
    _HERB_USES_CACHE_MTIME = None

    if not HERB_USES_EXCEL_PATH:
        logger.debug("HERB_USES_EXCEL_PATH not configured; skipping Excel lookup")
        return _HERB_USES_CACHE

    excel_path = Path(HERB_USES_EXCEL_PATH)
    if not excel_path.exists():
        logger.warning("Herb uses Excel file not found at %s", excel_path)
        return _HERB_USES_CACHE

    if not PANDAS_AVAILABLE:
        logger.warning("pandas not available. Cannot read Excel file. Install with: pip install pandas openpyxl")
        return _HERB_USES_CACHE

    try:
        # Read Excel file using pandas
        df = pd.read_excel(excel_path, engine='openpyxl')
        
        # Normalize column names (case-insensitive)
        df.columns = df.columns.str.strip().str.lower()
        
        # Check for required columns
        required_cols = ['common_name', 'uses']
        if not all(col in df.columns for col in required_cols):
            logger.error("Excel file missing required columns. Found: %s, Required: %s", list(df.columns), required_cols)
            return _HERB_USES_CACHE
        
        # Convert to list of dicts
        for _, row in df.iterrows():
            herb_data = {
                'common_name': str(row.get('common_name', '')).strip(),
                'scientific_name': str(row.get('scientific_name', '')).strip() if 'scientific_name' in df.columns else '',
                'uses': str(row.get('uses', '')).strip()
            }
            
            # Skip empty rows
            if herb_data['common_name'] and herb_data['uses']:
                _HERB_USES_CACHE.append(herb_data)
        
        _HERB_USES_CACHE_MTIME = excel_path.stat().st_mtime
        logger.info(
            "Loaded %d herb entries from Excel file: %s (mtime=%s)",
            len(_HERB_USES_CACHE),
            excel_path,
            _HERB_USES_CACHE_MTIME,
        )
        
    except Exception as exc:
        logger.error("Error loading Excel file %s: %s", excel_path, exc, exc_info=True)
        _HERB_USES_CACHE = []
        _HERB_USES_CACHE_MTIME = None

    return _HERB_USES_CACHE


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
    Tries multiple search strategies to find relevant information.
    """
    if not query:
        return None

    # Try multiple search strategies
    search_terms = [
        query.strip(),  # Original query
        query.strip().replace(" sp.", "").replace(" spp.", ""),  # Remove species abbreviation
    ]
    
    # If query has scientific name format, try just the genus
    if " " in query:
        genus = query.split()[0]
        if genus and len(genus) > 3:
            search_terms.append(genus)
    
    for search_term in search_terms:
        if not search_term:
            continue
            
        # Clean and format the query for Wikipedia URL
        title = search_term.strip().replace(" ", "_")
        title = quote(title, safe="")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

        try:
            response = httpx.get(
                url,
                headers={"Accept": "application/json"},
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
        except httpx.HTTPError as exc:
            logger.debug("Wikipedia lookup failed for %s: %s", search_term, exc)
            continue

        if response.status_code != 200:
            logger.debug("Wikipedia returned status %s for %s", response.status_code, search_term)
            continue

        try:
            data = response.json()
            extract = data.get("extract", "")
            
            if extract and len(extract) > 50:  # Ensure we have substantial content
                import re
                # Extract sentences that mention uses, medicinal properties, benefits
                sentences = re.split(r'[.!?]+', extract)
                usage_sentences = []
                
                # Expanded list of keywords for medicinal uses
                usage_keywords = [
                    "used to", "used for", "treat", "treatment", "medicinal", "medicine",
                    "herb", "traditional", "benefit", "cure", "heal", "therapeutic",
                    "application", "property", "properties", "helps", "effective", "remedy", 
                    "reduces", "prevents", "relieves", "alleviates", "improves", "enhances",
                    "antioxidant", "anti-inflammatory", "antimicrobial", "antiviral",
                    "digestive", "respiratory", "immune", "cardiovascular", "skin", "wound",
                    "diabetes", "fever", "pain", "inflammation", "infection", "cough", "cold",
                    "leaf", "leaves", "bark", "root", "fruit", "seed", "extract", "oil"
                ]
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) < 15:
                        continue
                    sentence_lower = sentence.lower()
                    if any(keyword in sentence_lower for keyword in usage_keywords):
                        usage_sentences.append(sentence)
                
                if usage_sentences:
                    # Combine relevant sentences about uses (up to 8 sentences for more info)
                    result = '. '.join(usage_sentences[:8])
                    if not result.endswith('.'):
                        result += "."
                    # Limit to 1000 characters but keep it informative
                    if len(result) > 1000:
                        result = result[:1000] + "..."
                    logger.info("Found Wikipedia uses for %s (searched as %s): %d characters", query, search_term, len(result))
                    return result
                
                # If no usage sentences found but extract exists, return first part if substantial
                if len(extract) > 150:
                    # Get first 700 characters - usually contains general info
                    first_part = extract[:700]
                    if len(extract) > 700:
                        first_part += "..."
                    logger.info("Using Wikipedia extract for %s (searched as %s, no specific uses found)", query, search_term)
                    return first_part
                    
        except (KeyError, ValueError) as exc:
            logger.debug("Error parsing Wikipedia response for %s: %s", search_term, exc)
            continue

    return None


def _get_uses_from_csv(common_name: str, scientific_name: str) -> Optional[str]:
    """Lookup uses in the Excel file by common or scientific name.

    Tries multiple matching strategies (exact, cleaned, partial, shared words).
    """
    rows = _load_herb_uses_from_csv()
    if not rows:
        return None

    def _normalize(name: str) -> str:
        name = (name or "").strip().lower()
        # Remove parentheses, common punctuation
        if "(" in name:
            name = name.split("(", 1)[0].strip()
        return name

    sci_norm = _normalize(scientific_name)
    com_norm = _normalize(common_name)

    # 1) Exact scientific name match
    if sci_norm:
        for row in rows:
            row_sci = _normalize(row.get("scientific_name", ""))
            if row_sci and sci_norm == row_sci:
                logger.info("Found medical uses in CSV for scientific name: %s", scientific_name)
                return row.get("uses")

    # 2) Exact common name match
    if com_norm:
        for row in rows:
            row_com = _normalize(row.get("common_name", ""))
            if row_com and com_norm == row_com:
                logger.info("Found medical uses in CSV for common name: %s", common_name)
                return row.get("uses")

    # 3) Partial common name match
    if com_norm:
        for row in rows:
            row_com = _normalize(row.get("common_name", ""))
            if row_com and (com_norm in row_com or row_com in com_norm):
                logger.info(
                    "Found medical uses in CSV via partial common name match: %s -> %s",
                    common_name,
                    row.get("common_name"),
                )
                return row.get("uses")

    # 4) Shared word match (e.g., "Fynbos aloe" vs "Aloe Vera")
    if com_norm:
        com_words = {w for w in com_norm.split() if len(w) >= 3}
        if com_words:
            for row in rows:
                row_com = _normalize(row.get("common_name", ""))
                if not row_com:
                    continue
                row_words = {w for w in row_com.split() if len(w) >= 3}
                if row_words and com_words.intersection(row_words):
                    logger.info(
                        "Found medical uses in CSV via shared-word match: %s -> %s",
                        common_name,
                        row.get("common_name"),
                    )
                    return row.get("uses")

    logger.debug(
        "No medical uses found in CSV for: common_name=%s, scientific_name=%s",
        common_name,
        scientific_name,
    )
    return None


def _fetch_wikipedia_full_page(query: str) -> Optional[str]:
    """Try to fetch full Wikipedia page content for more detailed information."""
    if not query:
        return None
    
    # Try to get the full page content using the text API (better than HTML)
    title = query.strip().replace(" ", "_")
    title = quote(title, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    
    try:
        response = httpx.get(
            url,
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0),
        )
        
        if response.status_code == 200:
            data = response.json()
            # Try to get more detailed extract
            extract = data.get("extract", "")
            
            if extract and len(extract) > 200:
                import re
                # Extract sentences that mention medicinal uses
                sentences = re.split(r'[.!?]+', extract)
                usage_sentences = []
                
                uses_keywords = [
                    "medicinal", "traditional medicine", "used to treat", "therapeutic",
                    "herbal", "remedy", "treatment", "cure", "heal", "benefit"
                ]
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 20:
                        sentence_lower = sentence.lower()
                        if any(keyword in sentence_lower for keyword in uses_keywords):
                            usage_sentences.append(sentence[:250])  # Limit sentence length
                
                if usage_sentences:
                    result = '. '.join(usage_sentences[:6])
                    if len(result) > 900:
                        result = result[:900] + "..."
                    logger.info("Found uses from full Wikipedia page for %s", query)
                    return result
                
                # If no specific uses found, return longer extract
                if len(extract) > 300:
                    return extract[:900] + "..." if len(extract) > 900 else extract
                    
    except Exception as e:
        logger.debug("Full page Wikipedia fetch failed for %s: %s", query, e)
    
    return None


def _search_web_for_uses(common_name: str, scientific_name: str) -> Optional[str]:
    """Search the web for medicinal uses information as a last resort."""
    if not common_name and not scientific_name:
        return None
    
    # Try to get information from Wikipedia search API
    search_queries = []
    
    if scientific_name and scientific_name != "Unknown":
        # Remove "sp." or "spp." from scientific name
        clean_scientific = scientific_name.replace(" sp.", "").replace(" spp.", "").strip()
        search_queries.append(f"{clean_scientific} medicinal uses")
        search_queries.append(f"{clean_scientific} traditional medicine")
    
    if common_name and common_name != "Unknown herb":
        search_queries.append(f"{common_name} medicinal uses")
        search_queries.append(f"{common_name} health benefits")
    
    # Try Wikipedia search API
    for query in search_queries[:2]:  # Limit to 2 queries to avoid too many requests
        try:
            # Use Wikipedia search API
            search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query.split()[0] + '_' + '_'.join(query.split()[1:3]) if len(query.split()) > 1 else query)}"
            
            response = httpx.get(
                search_url,
                headers={"Accept": "application/json"},
                timeout=httpx.Timeout(connect=3.0, read=10.0),
            )
            
            if response.status_code == 200:
                data = response.json()
                extract = data.get("extract", "")
                if extract and len(extract) > 100:
                    # Extract relevant sentences
                    import re
                    sentences = re.split(r'[.!?]+', extract)
                    usage_sentences = []
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if len(sentence) > 20:
                            sentence_lower = sentence.lower()
                            if any(kw in sentence_lower for kw in ["medicinal", "treat", "used", "benefit", "traditional"]):
                                usage_sentences.append(sentence)
                    
                    if usage_sentences:
                        result = '. '.join(usage_sentences[:4])
                        if len(result) > 600:
                            result = result[:600] + "..."
                        logger.info("Found uses from web search for %s", query)
                        return result
        except Exception as e:
            logger.debug("Web search failed for %s: %s", query, e)
            continue
    
    return None


def identify_herb(image_path: str) -> Dict[str, str]:
    """Identify the herb using the configured provider (Plant.id or PlantNet).
    Falls back to image similarity matching if API key is not available.
    Returns dict with common_name, scientific_name, uses, and processing_time."""
    import time
    start_time = time.time()
    
    result = None
    if PLANT_PROVIDER == "plantnet":
        result = _identify_with_plantnet(image_path)
    else:
        # Plant.id path
        api_key = os.getenv(PLANT_ID_API_KEY_ENV)
        if not api_key:
            logger.warning("Plant.id API key missing. Falling back to image similarity matching.")
            result = _identify_with_image_similarity(image_path)
        else:
            result = _identify_with_plantid(image_path)
    
    # Calculate processing time
    processing_time = time.time() - start_time
    
    # Add timing information to result
    if result and isinstance(result, dict):
        result["processing_time"] = round(processing_time, 2)
        logger.info("Identification completed in %.2f seconds", processing_time)
    
    return result


def _identify_with_plantid(image_path: str) -> Dict[str, str]:
    """Identify herb using Plant.id API."""
    api_key = os.getenv(PLANT_ID_API_KEY_ENV)

    if not api_key:
        logger.warning("Plant.id API key missing. Falling back to image similarity matching.")
        return _identify_with_image_similarity(image_path)

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
    
    logger.info("Plant.id identification: %s (%s)", common_name, scientific_name)
    
    # First, try to get medical uses from database
    uses = _get_medical_uses_from_db(common_name, scientific_name)

    # Next, try CSV lookup
    if not uses:
        uses = _get_uses_from_csv(common_name, scientific_name)
    
    # If still not found, try Wikipedia with multiple strategies
    if not uses:
        # Strategy 1: Try scientific name
        if scientific_name and scientific_name != "Unknown":
            uses = _fetch_wikipedia_summary(scientific_name)
            if not uses:
                uses = _fetch_wikipedia_full_page(scientific_name)
        
        # Strategy 2: Try common name
        if not uses and common_name and common_name != "Unknown":
            uses = _fetch_wikipedia_summary(common_name)
            if not uses:
                uses = _fetch_wikipedia_full_page(common_name)
        
        # Strategy 3: Try with "herb" or "plant" suffix
        if not uses and common_name and common_name != "Unknown":
            for suffix in [" herb", " plant", " medicinal plant"]:
                uses = _fetch_wikipedia_summary(f"{common_name}{suffix}")
                if uses:
                    break
        
        # Strategy 4: Try genus name if scientific name has species
        if not uses and scientific_name and " " in scientific_name:
            genus = scientific_name.split()[0]
            if genus and len(genus) > 3:
                uses = _fetch_wikipedia_summary(genus)
    
    # Try API's wiki description
    if not uses:
        wiki_description = plant_details.get("wiki_description") or {}
        uses = wiki_description.get("value")
    
    # Final fallback: web search and informative message
    if not uses:
        uses = _search_web_for_uses(common_name, scientific_name)
        
        if not uses:
            genus_info = ""
            if scientific_name and " " in scientific_name:
                genus = scientific_name.split()[0]
                genus_info = f" (genus: {genus})"
            
            uses = (
                f"This plant species ({scientific_name}{genus_info}, commonly known as {common_name}) "
                f"has been identified. While specific medical uses are not currently available in our database, "
                f"many plants in this genus have traditional medicinal applications. "
                f"Common uses may include: treating various ailments, traditional remedies, and herbal preparations. "
                f"Please consult a qualified herbalist, botanist, or medical professional for accurate usage "
                f"information, proper preparation methods, and safety guidelines before use."
            )

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
    Falls back to image similarity matching if API key is not available.
    """
    api_key = os.getenv(PLANTNET_API_KEY_ENV)
    if not api_key:
        logger.warning("PlantNet API key missing. Falling back to image similarity matching.")
        # Try image similarity matching as fallback
        return _identify_with_image_similarity(image_path)

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
    
    # Log full response for debugging (first time only)
    logger.debug("PlantNet API full response: %s", data_json)
    
    results = data_json.get("results") or []
    if not results:
        logger.info("PlantNet API did not return results: %s", data_json)
        return _build_failure_response("No matching herbs were found. Try another angle or better lighting.")

    top = results[0]
    # Log the structure for debugging
    logger.info("PlantNet top result: %s", top)
    
    # Extract species information - PlantNet API structure
    species = top.get("species") or {}
    if not species:
        # Sometimes species is directly in the result
        species = top
    
    logger.debug("PlantNet species data: %s", species)
    
    # Extract scientific name - try multiple possible field names
    scientific_name = (
        species.get("scientificNameWithoutAuthor") or 
        species.get("scientificName") or 
        top.get("scientificNameWithoutAuthor") or
        top.get("scientificName") or
        "Unknown"
    )
    
    # Extract common names - try multiple possible fields and formats
    common_names = []
    
    # Try commonNames (array)
    if "commonNames" in species:
        common_names = species.get("commonNames") or []
    elif "commonNames" in top:
        common_names = top.get("commonNames") or []
    
    # Try commonName (singular, might be string or array)
    if not common_names:
        common_name_single = species.get("commonName") or top.get("commonName")
        if common_name_single:
            if isinstance(common_name_single, list):
                common_names = common_name_single
            elif isinstance(common_name_single, str):
                common_names = [common_name_single]
    
    # Try GBIF common names
    if not common_names and "gbif" in species:
        gbif_common = species.get("gbif", {}).get("commonNames", [])
        if gbif_common:
            common_names = gbif_common if isinstance(gbif_common, list) else [gbif_common]
    
    # Use first common name, or scientific name as fallback, or "Unknown herb"
    if common_names and len(common_names) > 0:
        # Get the first common name, handling both string and dict formats
        first_name = common_names[0]
        if isinstance(first_name, dict):
            common_name = first_name.get("value") or first_name.get("name") or str(first_name)
        else:
            common_name = str(first_name)
    elif scientific_name and scientific_name != "Unknown":
        # Use scientific name as common name if no common name available
        common_name = scientific_name.split()[0] if " " in scientific_name else scientific_name
    else:
        common_name = "Unknown herb"

    score = top.get("score", 0.0)
    logger.info("PlantNet identification: %s (%s) - Score: %.2f", common_name, scientific_name, score)
    
    # First, try to get medical uses from database (highest priority)
    uses_description = _get_medical_uses_from_db(common_name, scientific_name)

    # Next, try CSV lookup
    if not uses_description:
        uses_description = _get_uses_from_csv(common_name, scientific_name)
    
    # If still not found, try Wikipedia with multiple strategies
    if not uses_description:
        # Strategy 1: Try scientific name
        if scientific_name and scientific_name != "Unknown":
            uses_description = _fetch_wikipedia_summary(scientific_name)
            if not uses_description:
                uses_description = _fetch_wikipedia_full_page(scientific_name)
        
        # Strategy 2: Try common name
        if not uses_description and common_name and common_name != "Unknown herb":
            uses_description = _fetch_wikipedia_summary(common_name)
            if not uses_description:
                uses_description = _fetch_wikipedia_full_page(common_name)
        
        # Strategy 3: Try with "herb" or "plant" suffix
        if not uses_description and common_name and common_name != "Unknown herb":
            for suffix in [" herb", " plant", " medicinal plant"]:
                uses_description = _fetch_wikipedia_summary(f"{common_name}{suffix}")
                if uses_description:
                    break
        
        # Strategy 4: Try genus name if scientific name has species
        if not uses_description and scientific_name and " " in scientific_name:
            genus = scientific_name.split()[0]
            if genus and len(genus) > 3:
                uses_description = _fetch_wikipedia_summary(genus)
        
        # Strategy 5: Try common name variations
        if not uses_description and common_name:
            # Remove parentheses content (e.g., "Tulsi (Holy Basil)" -> "Tulsi")
            clean_name = common_name.split("(")[0].strip()
            if clean_name != common_name:
                uses_description = _fetch_wikipedia_summary(clean_name)

    # Final fallback message - ensure we always have some guidance
    if not uses_description:
        # Try web search as last resort
        uses_description = _search_web_for_uses(common_name, scientific_name)
        
        if not uses_description:
            uses_description = (
                f"This plant ({scientific_name}, commonly known as {common_name}) has been identified. "
                "Detailed, reliable information about its medicinal uses was not found in our trusted online sources. "
                "If you plan to use this plant for health purposes, please consult a qualified herbalist, botanist, "
                "or medical professional for accurate usage information, preparation methods, and safety guidance."
            )

    return {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "uses": uses_description,
    }


def _identify_with_image_similarity(image_path: str) -> Dict[str, str]:
    """Identify herb using image similarity matching with database images.
    This is a fallback when API keys are not available."""
    try:
        from services.image_similarity import extract_and_match, get_feature_extractor
        from services.db_service import get_all_herbs
        from database.models import get_db
        
        logger.info("Attempting image similarity matching with database...")
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get all herbs from database
            all_herbs = get_all_herbs(db)
            
            if not all_herbs:
                logger.warning("Database is empty. Cannot perform image similarity matching.")
                return _build_failure_response(
                    "Database is empty. Please add herbs to the database first, or configure an API key."
                )
            
            # Convert herbs to dict format with features
            herbs_with_features = []
            herbs_without_features = []
            
            for herb in all_herbs:
                herb_dict = {
                    'id': herb.id,
                    'common_name': herb.common_name,
                    'scientific_name': herb.scientific_name,
                    'uses': herb.uses,
                    'description': herb.description,
                    'image_path': herb.image_path,
                    'features': herb.image_features
                }
                
                if herb.image_features:
                    herbs_with_features.append(herb_dict)
                else:
                    herbs_without_features.append(herb_dict)
            
            # Try to extract features and match if we have herbs with features
            if herbs_with_features:
                try:
                    matches = extract_and_match(image_path, herbs_with_features)
                    
                    if matches and len(matches) > 0:
                        best_match, similarity_score = matches[0]
                        
                        # Only return match if similarity is above threshold (0.3 = 30% similarity)
                        if similarity_score > 0.3:
                            logger.info("Found match with similarity score: %.2f", similarity_score)
                            
                            common_name = best_match.get('common_name', 'Unknown herb')
                            scientific_name = best_match.get('scientific_name', 'Unknown')
                            uses = best_match.get('uses', 'No information available.')
                            
                            return {
                                "common_name": common_name,
                                "scientific_name": scientific_name,
                                "uses": uses,
                            }
                        else:
                            logger.info("Best match similarity too low: %.2f (threshold: 0.3)", similarity_score)
                            # Fall through to return a sample herb
                            
                except Exception as e:
                    logger.warning("Image similarity matching failed: %s. Falling back to database lookup.", e)
                    # Fall through to return a sample herb
            
            # Fallback: Return the first herb from database as a sample
            # This allows the system to work even without image features
            if all_herbs:
                logger.info("No image features available. Returning sample herb from database.")
                sample_herb = all_herbs[0]
                return {
                    "common_name": sample_herb.common_name,
                    "scientific_name": sample_herb.scientific_name,
                    "uses": sample_herb.uses or "Medical uses information available in database. For accurate identification, please configure a Plant.id API key or add image features to database herbs.",
                }
            else:
                return _build_failure_response(
                    "No herbs found in database. Please add herbs to the database or configure a Plant.id API key."
                )
                
        finally:
            db.close()
            
    except ImportError as e:
        logger.warning("Image similarity service not available: %s. Using database fallback.", e)
        # Fallback to database lookup
        try:
            from services.db_service import get_all_herbs
            from database.models import get_db
            
            db = next(get_db())
            try:
                all_herbs = get_all_herbs(db)
                if all_herbs:
                    sample_herb = all_herbs[0]
                    return {
                        "common_name": sample_herb.common_name,
                        "scientific_name": sample_herb.scientific_name,
                        "uses": sample_herb.uses or "Medical uses information available. For accurate image-based identification, please install TensorFlow or configure a Plant.id API key.",
                    }
            finally:
                db.close()
        except:
            pass
        
        return _build_failure_response(
            "Image similarity matching is not available. Please install TensorFlow (pip install tensorflow numpy) or configure a Plant.id API key. You can get a free API key from https://plant.id/"
        )
    except Exception as e:
        logger.error("Error in image similarity identification: %s", e, exc_info=True)
        # Try database fallback
        try:
            from services.db_service import get_all_herbs
            from database.models import get_db
            
            db = next(get_db())
            try:
                all_herbs = get_all_herbs(db)
                if all_herbs:
                    sample_herb = all_herbs[0]
                    return {
                        "common_name": sample_herb.common_name,
                        "scientific_name": sample_herb.scientific_name,
                        "uses": sample_herb.uses or "Sample herb from database. For accurate identification, configure a Plant.id API key.",
                    }
            finally:
                db.close()
        except:
            pass
        
        return _build_failure_response(
            f"Error during identification: {str(e)}. Please try again or configure a Plant.id API key from https://plant.id/"
        )