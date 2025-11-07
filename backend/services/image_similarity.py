"""
Image similarity service for comparing uploaded images with database images.
Uses deep learning feature extraction to find the best match.
"""
import logging
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Optional
import pickle
import base64

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing import image

logger = logging.getLogger(__name__)

IMG_SIZE = (224, 224)


class ImageFeatureExtractor:
    """Extract features from images using a pre-trained CNN."""
    
    def __init__(self):
        # Use MobileNetV2 pre-trained on ImageNet for feature extraction
        # We'll use it without the classification head to get feature vectors
        self.base_model = MobileNetV2(
            weights='imagenet',
            include_top=False,
            pooling='avg',  # Global average pooling
            input_shape=(224, 224, 3)
        )
        # Freeze the model
        self.base_model.trainable = False
        logger.info("Image feature extractor initialized")
    
    def extract_features(self, image_path: str) -> np.ndarray:
        """
        Extract feature vector from an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Feature vector as numpy array (1280 dimensions for MobileNetV2)
        """
        try:
            # Load and preprocess image
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to model input size
            img = img.resize(IMG_SIZE)
            
            # Convert to array
            img_array = image.img_to_array(img)
            img_array = np.expand_dims(img_array, axis=0)
            
            # Preprocess for MobileNetV2
            img_array = preprocess_input(img_array)
            
            # Extract features
            features = self.base_model.predict(img_array, verbose=0)
            
            # Flatten and normalize
            features = features.flatten()
            features = features / (np.linalg.norm(features) + 1e-8)  # L2 normalization
            
            return features
        except Exception as e:
            logger.error("Error extracting features from %s: %s", image_path, e)
            raise
    
    def extract_features_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Extract features from image bytes."""
        import io
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.resize(IMG_SIZE)
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)
        features = self.base_model.predict(img_array, verbose=0)
        features = features.flatten()
        features = features / (np.linalg.norm(features) + 1e-8)
        return features


class ImageMatcher:
    """Match uploaded images with database images using feature similarity."""
    
    def __init__(self):
        self.feature_extractor = ImageFeatureExtractor()
    
    def calculate_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two feature vectors.
        
        Args:
            features1: First feature vector
            features2: Second feature vector
            
        Returns:
            Similarity score between 0 and 1 (1 = identical, 0 = completely different)
        """
        # Cosine similarity
        dot_product = np.dot(features1, features2)
        return float(dot_product)
    
    def find_best_match(
        self,
        query_features: np.ndarray,
        database_herbs: List[dict],
        top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """
        Find the best matching herbs from database.
        
        Args:
            query_features: Feature vector of the uploaded image
            database_herbs: List of herb dictionaries with 'features' key
            top_k: Number of top matches to return
            
        Returns:
            List of tuples (herb_dict, similarity_score) sorted by similarity
        """
        matches = []
        
        for herb in database_herbs:
            if not herb.get('features'):
                continue
            
            # Deserialize features if stored as string
            db_features = self._deserialize_features(herb['features'])
            if db_features is None:
                continue
            
            # Calculate similarity
            similarity = self.calculate_similarity(query_features, db_features)
            matches.append((herb, similarity))
        
        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches[:top_k]
    
    def _deserialize_features(self, features_data: str) -> Optional[np.ndarray]:
        """Deserialize feature vector from database."""
        try:
            if isinstance(features_data, bytes):
                return pickle.loads(features_data)
            elif isinstance(features_data, str):
                # Try base64 decode first
                try:
                    decoded = base64.b64decode(features_data)
                    return pickle.loads(decoded)
                except:
                    # Try direct pickle load
                    return pickle.loads(features_data.encode('latin1'))
            return None
        except Exception as e:
            logger.error("Error deserializing features: %s", e)
            return None
    
    def serialize_features(self, features: np.ndarray) -> str:
        """Serialize feature vector for database storage."""
        pickled = pickle.dumps(features)
        # Encode as base64 for safe storage
        return base64.b64encode(pickled).decode('utf-8')


# Global instances
_feature_extractor = None
_image_matcher = None


def get_feature_extractor() -> ImageFeatureExtractor:
    """Get or create feature extractor instance."""
    global _feature_extractor
    if _feature_extractor is None:
        _feature_extractor = ImageFeatureExtractor()
    return _feature_extractor


def get_image_matcher() -> ImageMatcher:
    """Get or create image matcher instance."""
    global _image_matcher
    if _image_matcher is None:
        _image_matcher = ImageMatcher()
    return _image_matcher


def extract_and_match(
    query_image_path: str,
    database_herbs: List[dict]
) -> List[Tuple[dict, float]]:
    """
    Extract features from query image and find best matches.
    
    Args:
        query_image_path: Path to uploaded image
        database_herbs: List of herbs from database with features
        
    Returns:
        List of (herb_dict, similarity_score) tuples
    """
    extractor = get_feature_extractor()
    matcher = get_image_matcher()
    
    # Extract features from query image
    query_features = extractor.extract_features(query_image_path)
    
    # Find best matches
    matches = matcher.find_best_match(query_features, database_herbs, top_k=5)
    
    return matches

