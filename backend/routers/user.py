from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
from services.herb_service import identify_herb
from schemas.herb_schema import HerbResponse

router = APIRouter(prefix="/user", tags=["User"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=HerbResponse)
async def upload_image(file: UploadFile = File(...)):
    # Save uploaded file temporarily
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Identify the herb
    herb_data = identify_herb(file_path)

    if not herb_data:
        raise HTTPException(status_code=400, detail="⚠️ Not a herb! Please try another image.")

    return herb_data
