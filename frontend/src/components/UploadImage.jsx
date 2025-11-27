import React, { useState, useRef } from "react";
import Webcam from "react-webcam";
import api from "../api/api";
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
    setResult(null);

    const formData = new FormData();
    formData.append("file", image);

    const startTime = Date.now();

    try {
      const { data } = await api.post("/predict", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);

      if (data?.error) {
        setError(data.error);
        setResult(null);
        return;
      }

      // Add client-side timing if server didn't provide it
      if (!data.processing_time) {
        data.processing_time = parseFloat(totalTime);
      }

      setResult(data);
      setError(null);
    } catch (err) {
      const message =
        err.response?.data?.error ||
        err.message ||
        "Error connecting to the server.";
      setError(message);
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
