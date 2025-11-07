"""
Training script for herb identification ML model.
This script trains a model using transfer learning on herb images.

Usage:
    python scripts/train_model.py --data_dir path/to/herb/images --epochs 10
"""
import sys
import argparse
import logging
from pathlib import Path
import numpy as np
from PIL import Image
import pickle

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "herb_model.h5"
CLASS_NAMES_PATH = MODEL_DIR / "class_names.pkl"

IMG_SIZE = (224, 224)
BATCH_SIZE = 32


def load_data(data_dir: Path):
    """Load and prepare training data from directory structure.
    
    Expected structure:
    data_dir/
        herb1/
            image1.jpg
            image2.jpg
        herb2/
            image1.jpg
            ...
    """
    logger.info("Loading data from %s", data_dir)
    
    # Get class names from subdirectories
    class_names = sorted([d.name for d in data_dir.iterdir() if d.is_dir()])
    logger.info("Found %d classes: %s", len(class_names), class_names)
    
    # Save class names
    with open(CLASS_NAMES_PATH, 'wb') as f:
        pickle.dump(class_names, f)
    logger.info("Saved class names to %s", CLASS_NAMES_PATH)
    
    # Create data generators with augmentation
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        horizontal_flip=True,
        zoom_range=0.2,
        validation_split=0.2
    )
    
    train_generator = train_datagen.flow_from_directory(
        data_dir,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )
    
    validation_generator = train_datagen.flow_from_directory(
        data_dir,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )
    
    return train_generator, validation_generator, class_names


def create_model(num_classes: int):
    """Create model using transfer learning."""
    logger.info("Creating model with %d classes", num_classes)
    
    # Use MobileNetV2 as base (pre-trained on ImageNet)
    base_model = MobileNetV2(
        weights='imagenet',
        include_top=False,
        input_shape=(224, 224, 3)
    )
    
    # Freeze base model layers initially
    base_model.trainable = False
    
    # Add custom classification head
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.5)(x)
    x = Dense(64, activation='relu')(x)
    x = Dropout(0.3)(x)
    predictions = Dense(num_classes, activation='softmax', name='predictions')(x)
    
    model = Model(inputs=base_model.input, outputs=predictions)
    
    # Compile model
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    logger.info("Model created successfully")
    return model


def train_model(data_dir: Path, epochs: int = 20):
    """Train the herb identification model."""
    # Load data
    train_gen, val_gen, class_names = load_data(data_dir)
    
    # Create model
    model = create_model(len(class_names))
    
    # Callbacks
    callbacks = [
        EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
        ModelCheckpoint(str(MODEL_PATH), monitor='val_accuracy', save_best_only=True)
    ]
    
    # Train model
    logger.info("Starting training for %d epochs", epochs)
    history = model.fit(
        train_gen,
        epochs=epochs,
        validation_data=val_gen,
        callbacks=callbacks,
        verbose=1
    )
    
    # Save final model
    model.save(str(MODEL_PATH))
    logger.info("Model saved to %s", MODEL_PATH)
    
    # Print final metrics
    logger.info("Training completed!")
    logger.info("Final training accuracy: %.2f%%", history.history['accuracy'][-1] * 100)
    logger.info("Final validation accuracy: %.2f%%", history.history['val_accuracy'][-1] * 100)
    
    return model, history


def main():
    parser = argparse.ArgumentParser(description='Train herb identification model')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Path to directory containing herb images organized by class')
    parser.add_argument('--epochs', type=int, default=20,
                        help='Number of training epochs (default: 20)')
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error("Data directory does not exist: %s", data_dir)
        return
    
    train_model(data_dir, args.epochs)


if __name__ == "__main__":
    main()

