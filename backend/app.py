from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil
import os

# Adjust the import according to your structure
from services.herb_service import identify_herb
from routers import user

app = FastAPI(title="🌿 Herbal Identification API")

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # later restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(user.router)

@app.get("/")
def root():
    return {"message": "✅ Herbal API is running successfully!"}

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    temp_dir = "uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = identify_herb(temp_path)
    os.remove(temp_path)   # Optional: clean up temp file

    if result:
        return result
    else:
        return JSONResponse({"error": "Unknown herb"}, status_code=400)
