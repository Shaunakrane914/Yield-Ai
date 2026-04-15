import { useState } from "react";
import { predictYield } from "@/shared/api/api";

const DISTRICTS = ["Cuttack", "Khordha", "Puri", "Sambalpur", "Balasore", "Ganjam"];
const CROPS = ["Paddy", "Maize", "Wheat", "Mustard", "Sugarcane"];
const SEASONS = ["Kharif", "Rabi", "Zaid"];

export function YieldPredictionPage() {
  const [district, setDistrict] = useState(DISTRICTS[0]);
  const [crop, setCrop] = useState(CROPS[0]);
  const [season, setSeason] = useState(SEASONS[0]);
  const [variety, setVariety] = useState("General");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const onPredict = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await predictYield({ district, crop, season, variety });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch prediction");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page">
      <h1>Yield Prediction</h1>
      <p className="lead">Run AI prediction based on district, crop, and season details.</p>

      <div className="grid">
        <div className="card">
          <label>District</label>
          <select value={district} onChange={(event) => setDistrict(event.target.value)}>
            {DISTRICTS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>

        <div className="card">
          <label>Crop</label>
          <select value={crop} onChange={(event) => setCrop(event.target.value)}>
            {CROPS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>

        <div className="card">
          <label>Season</label>
          <select value={season} onChange={(event) => setSeason(event.target.value)}>
            {SEASONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        <label htmlFor="variety">Variety</label>
        <input id="variety" value={variety} onChange={(event) => setVariety(event.target.value)} />
      </div>

      <div className="button-row">
        <button className="primary" type="button" onClick={onPredict} disabled={loading}>
          {loading ? "Predicting..." : "Predict Yield"}
        </button>
      </div>

      {error && <p className="status error">{error}</p>}

      {result && (
        <div className="card">
          <h3>Prediction Response</h3>
          <pre className="response">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
