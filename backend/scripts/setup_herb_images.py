"""
Script to link existing images to herbs and extract features.
This will make image similarity matching work.
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import get_db, init_db, Herb
from services.db_service import update_herb_features
from services.image_similarity import get_feature_extractor, get_image_matcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Map of image names to herb names (you can adjust this)
IMAGE_TO_HERB_MAP = {
    'tulsi.jpeg': 'Tulsi (Holy Basil)',
    'herb1.jpeg': 'Neem',  # Adjust based on actual images
    'herb3.jpeg': 'Aloe Vera',  # Adjust based on actual images
}


def setup_herb_images():
    """Link images to herbs and extract features."""
    init_db()
    db = next(get_db())
    
    try:
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        
        if not uploads_dir.exists():
            logger.error("Uploads directory not found: %s", uploads_dir)
            return
        
        extractor = get_feature_extractor()
        matcher = get_image_matcher()
        
        # Get all images in uploads folder
        image_files = list(uploads_dir.glob("*.jpeg")) + list(uploads_dir.glob("*.jpg")) + list(uploads_dir.glob("*.png"))
        logger.info("Found %d images in uploads folder", len(image_files))
        
        updated_count = 0
        
        for image_path in image_files:
            # Try to match image to herb by name
            image_name = image_path.name.lower()
            matched_herb = None
            
            # First try exact match from map
            for img_key, herb_name in IMAGE_TO_HERB_MAP.items():
                if img_key.lower() in image_name:
                    matched_herb = db.query(Herb).filter(
                        Herb.common_name.ilike(f"%{herb_name}%")
                    ).first()
                    break
            
            # If no match from map, try to find herb by image name
            if not matched_herb:
                # Try to match by common name in image filename
                for herb in db.query(Herb).all():
                    herb_name_lower = herb.common_name.lower()
                    # Check if any word from herb name is in image name
                    herb_words = herb_name_lower.split()
                    for word in herb_words:
                        if len(word) > 3 and word in image_name:
                            matched_herb = herb
                            break
                    if matched_herb:
                        break
            
            if not matched_herb:
                logger.warning("Could not match image %s to any herb", image_path.name)
                continue
            
            try:
                logger.info("Processing %s -> %s", image_path.name, matched_herb.common_name)
                
                # Extract features
                features = extractor.extract_features(str(image_path))
                features_serialized = matcher.serialize_features(features)
                
                # Update herb with image path and features
                matched_herb.image_path = str(image_path)
                matched_herb.image_features = features_serialized
                db.commit()
                
                updated_count += 1
                logger.info("✓ Updated %s with image and features", matched_herb.common_name)
                
            except Exception as e:
                logger.error("Error processing %s: %s", image_path.name, e, exc_info=True)
        
        logger.info("\n" + "="*50)
        logger.info("Setup completed!")
        logger.info("Updated %d herbs with images and features", updated_count)
        logger.info("="*50)
        
    finally:
        db.close()


if __name__ == "__main__":
    setup_herb_images()

