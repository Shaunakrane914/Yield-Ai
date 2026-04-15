import { useMemo } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, Polygon, TileLayer } from "react-leaflet";
import { clearStoredFarm, getStoredFarm } from "@/shared/lib/farmStorage";
import type { LatLng } from "@/shared/types/types";

export function DashboardPage() {
  const farm = getStoredFarm();

  const center = useMemo<[number, number]>(() => {
    if (!farm || farm.boundaryPoints.length === 0) {
      return [20.9517, 85.0985];
    }
    const avgLat = farm.boundaryPoints.reduce((sum, point) => sum + point.lat, 0) / farm.boundaryPoints.length;
    const avgLng = farm.boundaryPoints.reduce((sum, point) => sum + point.lng, 0) / farm.boundaryPoints.length;
    return [avgLat, avgLng];
  }, [farm]);

  const resetFarm = () => {
    clearStoredFarm();
    window.location.href = "/setup";
  };

  if (!farm || farm.boundaryPoints.length < 3) {
    return (
      <section className="page">
        <h1>Farm Dashboard</h1>
        <p className="lead">No farm found yet. Start with setup to unlock your dashboard.</p>
        <div className="card">
          <p>Your session starts fresh for each new visitor. Set up your farm first.</p>
          <Link className="inline-link" to="/setup">
            Go to Farm Setup
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <h1>Farm Dashboard</h1>
      <p className="lead">Welcome back! Here is your saved farm boundary and local dashboard snapshot.</p>

      <div className="card">
        <p>
          <strong>Farm Name:</strong> {farm.farmName}
        </p>
        <p>
          <strong>Boundary Points:</strong> {farm.boundaryPoints.length}
        </p>
        <p>
          <strong>Last Updated:</strong> {new Date(farm.updatedAt).toLocaleString()}
        </p>
        <div className="button-row">
          <button type="button" onClick={resetFarm}>
            Re-setup Farm
          </button>
          <Link className="inline-link" to="/predict">
            Continue to Yield Prediction
          </Link>
        </div>
      </div>

      <div className="map-shell">
        <MapContainer center={center} zoom={14} className="map">
          <TileLayer
            attribution="Tiles &copy; Esri"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
          {farm.boundaryPoints.map((point: LatLng, index: number) => (
            <Marker key={`${point.lat}-${point.lng}-${index}`} position={[point.lat, point.lng]} />
          ))}
          <Polygon
            positions={farm.boundaryPoints.map((point: LatLng) => [point.lat, point.lng])}
            pathOptions={{ color: "#2f855a", fillColor: "#68d391", fillOpacity: 0.3 }}
          />
        </MapContainer>
        <p className="hint">This is your current farm view saved in local browser storage.</p>
      </div>
    </section>
  );
}
