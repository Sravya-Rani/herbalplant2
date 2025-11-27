import os
import logging
import numpy as np
from PIL import Image
import pickle
from pathlib import Path
from typing import Dict, Optional, Tuple
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model

logger = logging.getLogger(__name__)

# Model configuration
MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
MODEL_PATH = MODEL_DIR / "herb_model.h5"
CLASS_NAMES_PATH = MODEL_DIR / "class_names.pkl"
IMG_SIZE = (224, 224)


class HerbMLModel:
    """Machine Learning model for herb identification using transfer learning."""
    
    def __init__(self):
        self.model = None
        self.class_names = []
        self.base_model = None
        self._load_or_create_model()
    
    def _load_or_create_model(self):
        """Load existing model or create a new one."""
        try:
            if MODEL_PATH.exists() and CLASS_NAMES_PATH.exists():
                logger.info("Loading existing model from %s", MODEL_PATH)
                self.model = keras.models.load_model(str(MODEL_PATH))
                with open(CLASS_NAMES_PATH, 'rb') as f:
                    self.class_names = pickle.load(f)
                logger.info("Model loaded successfully with %d classes", len(self.class_names))
            else:
                logger.info("No existing model found. Creating new model structure.")
                self._create_model_structure()
        except Exception as e:
            logger.error("Error loading model: %s", e)
            self._create_model_structure()
    
    def _create_model_structure(self):
        """Create a new model structure using transfer learning."""
        # Use MobileNetV2 as base (pre-trained on ImageNet)
        self.base_model = MobileNetV2(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
        
        # Freeze base model layers
        self.base_model.trainable = False
        
        # Add custom classification head
        x = self.base_model.output
        x = GlobalAveragePooling2D()(x)
        x = Dense(128, activation='relu')(x)
        x = Dense(64, activation='relu')(x)
        predictions = Dense(10, activation='softmax', name='predictions')(x)  # Default 10 classes
        
        self.model = Model(inputs=self.base_model.input, outputs=predictions)
        
        # Compile model
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info("New model structure created")
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for model prediction."""
        try:
            img = Image.open(image_path)
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Resize to model input size
            img = img.resize(IMG_SIZE)
            # Convert to array
            img_array = image.img_to_array(img)
            # Expand dimensions for batch
            img_array = np.expand_dims(img_array, axis=0)
            # Preprocess for MobileNetV2
            img_array = preprocess_input(img_array)
            return img_array
        except Exception as e:
            logger.error("Error preprocessing image: %s", e)
            raise
    
    def predict(self, image_path: str, top_k: int = 3) -> list:
        """Predict herb class from image."""
        if self.model is None:
            raise ValueError("Model not loaded or created")
        
        try:
            # Preprocess image
            img_array = self.preprocess_image(image_path)
            
            # Get predictions
            predictions = self.model.predict(img_array, verbose=0)
            
            # Get top k predictions
            top_indices = np.argsort(predictions[0])[-top_k:][::-1]
            top_predictions = []
            
            for idx in top_indices:
                if idx < len(self.class_names):
                    confidence = float(predictions[0][idx])
                    class_name = self.class_names[idx] if self.class_names else f"Class_{idx}"
                    top_predictions.append({
                        'class': class_name,
                        'confidence': confidence
                    })
            
            return top_predictions
        except Exception as e:
            logger.error("Error during prediction: %s", e)
            raise
    
    def save_model(self, model_path: str = None, class_names: list = None):
        """Save model and class names."""
        if model_path is None:
            model_path = MODEL_PATH
        
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        if self.model:
            self.model.save(str(model_path))
            logger.info("Model saved to %s", model_path)
        
        if class_names:
            self.class_names = class_names
            with open(CLASS_NAMES_PATH, 'wb') as f:
                pickle.dump(class_names, f)
            logger.info("Class names saved to %s", CLASS_NAMES_PATH)


# Global model instance
_ml_model = None


def get_ml_model() -> HerbMLModel:
    """Get or create ML model instance."""
    global _ml_model
    if _ml_model is None:
        _ml_model = HerbMLModel()
    return _ml_model


def identify_herb_ml(image_path: str) -> Optional[Dict[str, any]]:
    """Identify herb using ML model."""
    try:
        model = get_ml_model()
        predictions = model.predict(image_path, top_k=1)
        
        if predictions and len(predictions) > 0:
            top_pred = predictions[0]
            return {
                'class': top_pred['class'],
                'confidence': top_pred['confidence']
            }
        return None
    except Exception as e:
        logger.error("ML identification error: %s", e)
        return None

