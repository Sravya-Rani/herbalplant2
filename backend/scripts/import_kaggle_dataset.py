"""
Script to import herb images from Kaggle dataset into the database.
This script processes images, extracts features, and stores them in the database.

Usage:
    python scripts/import_kaggle_dataset.py --dataset_dir path/to/kaggle/dataset
"""
import sys
import argparse
import logging
from pathlib import Path
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import get_db, init_db
from services.db_service import create_herb, get_herb_by_name
from services.image_similarity import get_feature_extractor, get_image_matcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}


def process_kaggle_dataset(dataset_dir: Path):
    """
    Process Kaggle dataset and import into database.
    
    Expected structure:
    dataset_dir/
        herb_name1/
            image1.jpg
            image2.jpg
        herb_name2/
            image1.jpg
            ...
    """
    logger.info("Processing Kaggle dataset from: %s", dataset_dir)
    
    if not dataset_dir.exists():
        logger.error("Dataset directory does not exist: %s", dataset_dir)
        return
    
    # Initialize database
    init_db()
    db = next(get_db())
    
    # Initialize feature extractor
    extractor = get_feature_extractor()
    matcher = get_image_matcher()
    
    # Process each herb directory
    herb_dirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
    logger.info("Found %d herb directories", len(herb_dirs))
    
    total_images = 0
    total_herbs = 0
    
    for herb_dir in herb_dirs:
        herb_name = herb_dir.name
        logger.info("Processing herb: %s", herb_name)
        
        # Get all images in this directory
        image_files = [
            f for f in herb_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        
        if not image_files:
            logger.warning("No images found in %s", herb_dir)
            continue
        
        logger.info("Found %d images for %s", len(image_files), herb_name)
        
        # Check if herb already exists
        existing_herb = get_herb_by_name(db, herb_name)
        
        if existing_herb:
            logger.info("Herb %s already exists, skipping", herb_name)
            continue
        
        # Use first image to extract features
        first_image = image_files[0]
        try:
            features = extractor.extract_features(str(first_image))
            features_serialized = matcher.serialize_features(features)
        except Exception as e:
            logger.error("Error extracting features from %s: %s", first_image, e)
            features_serialized = None
        
        # Create herb entry
        # Try to extract scientific name from directory name or use common name
        scientific_name = herb_name.replace('_', ' ').title()
        
        herb = create_herb(
            db=db,
            common_name=herb_name.replace('_', ' ').title(),
            scientific_name=scientific_name,
            uses=f"Information about {herb_name}. Please add detailed uses information.",
            description=f"Herb imported from Kaggle dataset: {herb_name}",
            image_path=str(first_image),
            image_features=features_serialized
        )
        
        total_herbs += 1
        total_images += len(image_files)
        
        logger.info("Imported herb: %s with %d images", herb_name, len(image_files))
    
    logger.info("Import completed!")
    logger.info("Total herbs imported: %d", total_herbs)
    logger.info("Total images processed: %d", total_images)


def main():
    parser = argparse.ArgumentParser(description='Import Kaggle dataset into database')
    parser.add_argument('--dataset_dir', type=str, required=True,
                        help='Path to Kaggle dataset directory')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset_dir)
    process_kaggle_dataset(dataset_dir)


if __name__ == "__main__":
    main()

