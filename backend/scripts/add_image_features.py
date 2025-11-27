"""
Script to add image features to existing herbs in database.
Use this if you've added herbs without features, or want to update features.

Usage:
    python scripts/add_image_features.py
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import get_db, init_db
from services.db_service import get_all_herbs, update_herb_features
from services.image_similarity import get_feature_extractor, get_image_matcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_features_to_existing_herbs():
    """Add image features to herbs that don't have them."""
    init_db()
    db = next(get_db())
    
    herbs = get_all_herbs(db)
    logger.info("Found %d herbs in database", len(herbs))
    
    extractor = get_feature_extractor()
    matcher = get_image_matcher()
    
    updated_count = 0
    skipped_count = 0
    
    for herb in herbs:
        if herb.image_features:
            logger.info("Herb %s already has features, skipping", herb.common_name)
            skipped_count += 1
            continue
        
        if not herb.image_path or not Path(herb.image_path).exists():
            logger.warning("No valid image path for %s, skipping", herb.common_name)
            skipped_count += 1
            continue
        
        try:
            logger.info("Extracting features for %s from %s", herb.common_name, herb.image_path)
            features = extractor.extract_features(herb.image_path)
            features_serialized = matcher.serialize_features(features)
            
            if update_herb_features(db, herb.id, features_serialized):
                updated_count += 1
                logger.info("Updated features for %s", herb.common_name)
        except Exception as e:
            logger.error("Error processing %s: %s", herb.common_name, e)
            skipped_count += 1
    
    logger.info("Processing completed!")
    logger.info("Updated: %d, Skipped: %d", updated_count, skipped_count)


if __name__ == "__main__":
    add_features_to_existing_herbs()

