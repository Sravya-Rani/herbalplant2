import React, { useState, useRef } from "react";
import Webcam from "react-webcam";
import ResultCard from "./ResultCard"; // Import your ResultCard
import "../index.css";

function UploadImage() {
  const [image, setImage] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false); // added loading state
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const webcamRef = useRef(null);

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    setImage(file);
    setResult(null);
    setError(null);
  };

  const capturePhoto = () => {
    const imageSrc = webcamRef.current.getScreenshot();
    fetch(imageSrc)
      .then((res) => res.blob())
      .then((blob) => {
        const file = new File([blob], "photo.jpg", { type: "image/jpeg" });
        setImage(file);
        setResult(null);
        setError(null);
        setIsCameraOpen(false);
      });
  };

  const uploadToBackend = async () => {
    if (!image) {
      setError("Please upload or capture an image first.");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", image);

    try {
      const response = await fetch("http://127.0.0.1:8000/predict", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setResult(null);
      } else {
        setResult(data);
        setError(null);
      }
    } catch (err) {
      setError("Error connecting to the server.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="herbal-container">
      <div className="herbal-card">
        <h1 className="herbal-title">🌿 Herbal Identification System</h1>
        <p className="subtitle">Upload or capture an image to identify your herb</p>

        <div className="button-group">
          <label htmlFor="upload" className="btn upload-btn">
            Upload Image
          </label>
          <input
            id="upload"
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            style={{ display: "none" }}
          />

          <button
            className="btn camera-btn"
            onClick={() => setIsCameraOpen(!isCameraOpen)}
          >
            {isCameraOpen ? "Close Camera" : "Take Photo"}
          </button>
        </div>

        {isCameraOpen && (
          <div className="webcam-container">
            <Webcam ref={webcamRef} screenshotFormat="image/jpeg" className="webcam" />
            <button className="btn capture-btn" onClick={capturePhoto}>
              📸 Capture
            </button>
          </div>
        )}

        {image && (
          <div className="preview-section">
            <img
              src={URL.createObjectURL(image)}
              alt="preview"
              className="preview-img"
            />
            <div className="center-btn">
              <button className="btn upload-main-btn" onClick={uploadToBackend} disabled={loading}>
                {loading ? "Identifying..." : "🔍 Identify Herb"}
              </button>
            </div>
          </div>
        )}

        {error && <p className="error-message">⚠️ {error}</p>}

        {result && <ResultCard data={result} />}
      </div>
    </div>
  );
}

export default UploadImage;
