import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapPicker } from "@/shared/components/MapPicker";
import { saveStoredFarm } from "@/shared/lib/farmStorage";
import type { LatLng } from "@/shared/types/types";

export function FarmSetupPage() {
  const navigate = useNavigate();
  const [farmName, setFarmName] = useState("");
  const [points, setPoints] = useState<LatLng[]>([]);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const canSubmit = useMemo(() => farmName.trim().length > 0 && points.length >= 3, [farmName, points]);

  const removeLastPoint = () => {
    setPoints((prev) => prev.slice(0, -1));
  };

  const clearAllPoints = () => {
    setPoints([]);
  };

  const handleSubmit = async () => {
    if (!canSubmit) {
      setStatus("Enter farm name and draw at least 3 points.");
      return;
    }

    setLoading(true);
    setStatus("Saving farm setup...");
    saveStoredFarm(farmName, points);
    setStatus("Farm setup saved. Taking you to dashboard...");
    setLoading(false);
    navigate("/dashboard");
  };

  return (
    <section className="page">
      <h1>Farm Setup</h1>
      <p className="lead">Welcome! Mark your farm boundary on the map to get started.</p>

      <div className="card">
        <label htmlFor="farm-name">Farm Name</label>
        <input
          id="farm-name"
          value={farmName}
          onChange={(event) => setFarmName(event.target.value)}
          placeholder="Example: East Paddy Plot"
        />
      </div>

      <MapPicker points={points} onChange={setPoints} />

      <div className="button-row">
        <button type="button" onClick={removeLastPoint} disabled={points.length === 0}>
          Remove Last Point
        </button>
        <button type="button" onClick={clearAllPoints} disabled={points.length === 0}>
          Clear All
        </button>
        <button type="button" className="primary" onClick={handleSubmit} disabled={loading || !canSubmit}>
          {loading ? "Saving..." : "Save Farm"}
        </button>
      </div>

      <p className="status">{status || `Boundary points selected: ${points.length}`}</p>
    </section>
  );
}
