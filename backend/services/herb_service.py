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


def identify_herb(image_path: str) -> Dict[str, str]:
    """Identify the herb using the configured provider (Plant.id or PlantNet).
    Falls back to image similarity matching if API key is not available."""
    if PLANT_PROVIDER == "plantnet":
        return _identify_with_plantnet(image_path)
    
    # default path: Plant.id
    api_key = os.getenv(PLANT_ID_API_KEY_ENV)

    if not api_key:
        logger.warning("Plant.id API key missing. Falling back to image similarity matching.")
        # Try image similarity matching as fallback
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
    
    # First, try to get medical uses from database
    uses = _get_medical_uses_from_db(common_name, scientific_name)
    
    # If not found in database, try Wikipedia
    if not uses:
        if scientific_name and scientific_name != "Unknown":
            uses = _fetch_wikipedia_summary(scientific_name)
        
        if not uses and common_name and common_name != "Unknown":
            uses = _fetch_wikipedia_summary(common_name)
    
    # Final fallback: use API's wiki description or default message
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
    
    # If not found in database, try Wikipedia
    if not uses_description:
        # First try scientific name, then common name
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
