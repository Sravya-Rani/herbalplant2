# Herbal Plant Identification - Image Similarity Matching with Kaggle Dataset

This project uses **Machine Learning** and **Database** for herb identification by comparing uploaded images with images from a Kaggle dataset.

## Architecture

1. **Image Feature Extraction**: Uses MobileNetV2 (pre-trained CNN) to extract feature vectors from images
2. **Image Similarity Matching**: Compares uploaded image features with database image features using cosine similarity
3. **Database**: SQLite database storing herb images, features, and information
4. **Workflow**: 
   - Upload image → Extract features
   - Compare with all images in database
   - Find best match (highest similarity)
   - Return herb information

## How It Works

### Image Similarity Matching
- Uses **MobileNetV2** (pre-trained on ImageNet) to extract 1280-dimensional feature vectors
- Compares feature vectors using **cosine similarity**
- Returns the herb with the highest similarity score
- No training required - uses pre-trained model for feature extraction

### Database Structure
- Stores herb images and their extracted features
- Each herb has: common_name, scientific_name, uses, description, image_path, image_features
- Features are stored as serialized vectors for fast comparison

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Note**: TensorFlow installation may take some time. If you encounter issues, you can use:
```bash
pip install tensorflow-cpu==2.15.0  # For CPU-only systems
```

### 2. Download Kaggle Dataset

1. Download a herb/plant image dataset from Kaggle
2. Extract it to a directory (e.g., `kaggle_herbs/`)
3. Expected structure:
   ```
   kaggle_herbs/
       herb_name1/
           image1.jpg
           image2.jpg
       herb_name2/
           image1.jpg
           ...
   ```

### 3. Import Kaggle Dataset into Database

Run the import script to process images and store them in the database:

```bash
python scripts/import_kaggle_dataset.py --dataset_dir path/to/kaggle_herbs
```

This script will:
- Process each herb directory
- Extract features from images using MobileNetV2
- Store herb information and features in the database
- Use the first image of each herb as the reference image

### 4. Initialize Database (Optional - for sample data)

If you want to start with sample data:

```bash
python scripts/init_database.py
```

Then add features to existing herbs:

```bash
python scripts/add_image_features.py
```

### 5. Start the Backend Server

```bash
uvicorn app:app --reload
```

The API will be available at `http://127.0.0.1:8000`

## Usage

### Upload Image for Identification

1. Upload an image via the frontend or API endpoint `/predict`
2. The system will:
   - Extract features from your uploaded image
   - Compare with all images in the database
   - Find the best match (highest similarity)
   - Return herb information (name, scientific name, uses)

### API Endpoints

- `GET /` - Health check
- `POST /predict` - Upload image and get herb identification
- `POST /user/upload` - Alternative upload endpoint

## Project Structure

```
backend/
├── database/
│   ├── models.py              # SQLAlchemy models (with image_features field)
│   ├── __init__.py
│   └── herbs.db               # SQLite database
├── services/
│   ├── image_similarity.py    # Feature extraction and similarity matching
│   ├── db_service.py          # Database operations
│   └── herb_service.py        # Main identification service (uses similarity)
├── scripts/
│   ├── import_kaggle_dataset.py  # Import Kaggle dataset
│   ├── add_image_features.py      # Add features to existing herbs
│   └── init_database.py           # Initialize database
└── app.py                         # FastAPI application
```

## Key Features

1. **No Training Required**: Uses pre-trained MobileNetV2 for feature extraction
2. **Image Similarity**: Compares uploaded images with database images
3. **Best Match**: Returns the herb with highest similarity score
4. **Scalable**: Easy to add more herbs from Kaggle datasets
5. **Fast**: Feature extraction and comparison are efficient

## Adding More Herbs

### From Kaggle Dataset
```bash
python scripts/import_kaggle_dataset.py --dataset_dir path/to/new/dataset
```

### Manually
1. Add herb to database with image path
2. Run feature extraction:
```bash
python scripts/add_image_features.py
```

## Notes for Faculty Presentation

1. **Machine Learning**: Uses deep learning (CNN) for feature extraction
2. **Algorithm**: MobileNetV2 (pre-trained on ImageNet) + Cosine Similarity
3. **Database**: SQLite with image features stored for fast comparison
4. **Matching Method**: Image similarity matching (not classification)
5. **Dataset**: Uses Kaggle datasets for herb images
6. **No Training**: Uses transfer learning - no model training required

## Troubleshooting

- **No matches found**: Ensure database has herbs with image features. Run `add_image_features.py`
- **Low similarity scores**: Images may not match well. Try clearer images or add more similar herbs to database
- **Database errors**: Run `python scripts/init_database.py` to recreate database
- **TensorFlow issues**: Ensure Python 3.8-3.11 and install TensorFlow CPU version if needed

## Example Kaggle Datasets

Some good Kaggle datasets for herbs/plants:
- PlantNet dataset
- Medicinal plants dataset
- Herbal plants image dataset
- Indian medicinal plants dataset

Make sure the dataset has images organized by herb/plant name in separate folders.
