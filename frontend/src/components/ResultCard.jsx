import React from "react";

const ResultCard = ({ data }) => {
  const isUnknown = (data.scientific_name || "").toLowerCase() === "n/a" || 
                     (data.scientific_name || "").toLowerCase() === "unknown";

  return (
    <div style={styles.card}>
      <h3>{isUnknown ? "⚠️ Herb Not Identified" : "✅ Herb Identified"}</h3>
      
      <div style={styles.infoSection}>
        <p style={styles.infoRow}>
          <strong style={styles.label}>Common Name:</strong> 
          <span style={styles.value}>{data.common_name || "Not available"}</span>
        </p>
        
        <p style={styles.infoRow}>
          <strong style={styles.label}>Scientific Name:</strong> 
          <span style={styles.value}>{data.scientific_name || "Not available"}</span>
        </p>
        
        <div style={styles.usesSection}>
          <strong style={styles.label}>Medical Uses & Benefits:</strong>
          <p style={styles.usesText}>{data.uses || "Information not available"}</p>
        </div>
        
        {data.processing_time && (
          <p style={styles.timing}>
            ⏱️ Identified in {data.processing_time} seconds
          </p>
        )}
      </div>
    </div>
  );
};

const styles = {
  card: {
    backgroundColor: "#e8f5e9",
    border: "1px solid #2db832ff",
    borderRadius: "10px",
    padding: "20px",
    maxWidth: "600px",
    width: "100%",
    margin: "20px auto",
    boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
    textAlign: "left",
  },
  infoSection: {
    marginTop: "15px",
  },
  infoRow: {
    margin: "12px 0",
    lineHeight: "1.6",
  },
  label: {
    color: "#2e6f33",
    display: "inline-block",
    minWidth: "140px",
    marginRight: "10px",
  },
  value: {
    color: "#264d26",
    fontWeight: "500",
  },
  usesSection: {
    marginTop: "20px",
    paddingTop: "15px",
    borderTop: "1px solid #96cfa0",
  },
  usesText: {
    marginTop: "10px",
    color: "#264d26",
    lineHeight: "1.8",
    textAlign: "justify",
    whiteSpace: "pre-wrap",
  },
  timing: {
    marginTop: "15px",
    paddingTop: "10px",
    borderTop: "1px dashed #96cfa0",
    color: "#4a7b44",
    fontSize: "0.9em",
    fontStyle: "italic",
    textAlign: "center",
  },
};

export default ResultCard;

