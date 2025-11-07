import base64
import logging
import os
import mimetypes
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

import httpx

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    load_dotenv = None

logger = logging.getLogger(__name__)

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


def identify_herb(image_path: str) -> Dict[str, str]:
    """Identify the herb using the configured provider (Plant.id or PlantNet)."""
    if PLANT_PROVIDER == "plantnet":
        return _identify_with_plantnet(image_path)
    
    # default path: Plant.id
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
    
    # Try to get usage information from Wikipedia
    # First try scientific name, then common name
    uses_description = None
    if scientific_name and scientific_name != "Unknown":
        uses_description = _fetch_wikipedia_summary(scientific_name)
    
    if not uses_description and common_name and common_name != "Unknown herb":
        uses_description = _fetch_wikipedia_summary(common_name)
    
    # If still no description, try with "herb" or "plant" suffix
    if not uses_description and common_name and common_name != "Unknown herb":
        for suffix in [" herb", " plant", ""]:
            uses_description = _fetch_wikipedia_summary(f"{common_name}{suffix}")
            if uses_description:
                break

    # Final fallback with score information
    if not uses_description:
        if isinstance(score, (int, float)):
            uses_description = (
                f"Confidence score: {round(score * 100)}%. "
                f"This plant ({scientific_name}) has been identified. "
                f"Please consult a botanical reference for detailed usage information."
            )
        else:
            uses_description = (
                f"This plant ({scientific_name}) has been identified. "
                f"Please consult a botanical reference for detailed usage information."
            )

    return {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "uses": uses_description,
    }
