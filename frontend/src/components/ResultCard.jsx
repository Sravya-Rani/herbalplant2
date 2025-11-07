import React from "react";

const ResultCard = ({ data }) => {
  const isUnknown = (data.scientific_name || "").toLowerCase() === "n/a";

  return (
    <div style={styles.card}>
      <h3>{isUnknown ? "⚠️ Herb Not Identified" : "✅ Herb Identified"}</h3>
      <p>
        <strong>Common Name:</strong> {data.common_name}
      </p>
      <p>
        <strong>Scientific Name:</strong> {data.scientific_name}
      </p>
      <p>
        <strong>Uses:</strong> {data.uses}
      </p>
    </div>
  );
};

const styles = {
  card: {
    backgroundColor: "#e8f5e9",
    border: "1px solid #2db832ff",
    borderRadius: "10px",
    padding: "20px",
    width: "300px",
    margin: "20px auto",
    boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
    textAlign: "left",
  },
};

export default ResultCard;

