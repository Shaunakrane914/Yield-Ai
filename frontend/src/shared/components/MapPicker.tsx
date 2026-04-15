import { useMemo } from "react";
import { MapContainer, Marker, Polygon, TileLayer, useMapEvents } from "react-leaflet";
import type { LatLng } from "@/shared/types/types";
import "leaflet/dist/leaflet.css";

type MapPickerProps = {
  points: LatLng[];
  onChange: (points: LatLng[]) => void;
};

function ClickRecorder({ points, onChange }: MapPickerProps) {
  useMapEvents({
    click(event) {
      onChange([...points, { lat: event.latlng.lat, lng: event.latlng.lng }]);
    },
  });
  return null;
}

export function MapPicker({ points, onChange }: MapPickerProps) {
  const center = useMemo<[number, number]>(() => {
    if (points.length > 0) {
      return [points[0].lat, points[0].lng];
    }
    return [20.9517, 85.0985];
  }, [points]);

  return (
    <div className="map-shell">
      <MapContainer center={center} zoom={7} className="map">
        <TileLayer
          attribution="Tiles &copy; Esri"
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
        <ClickRecorder points={points} onChange={onChange} />
        {points.map((point, index) => (
          <Marker key={`${point.lat}-${point.lng}-${index}`} position={[point.lat, point.lng]} />
        ))}
        {points.length >= 3 && (
          <Polygon
            positions={points.map((point) => [point.lat, point.lng])}
            pathOptions={{ color: "#2f855a", fillColor: "#68d391", fillOpacity: 0.3 }}
          />
        )}
      </MapContainer>
      <p className="hint">Click on map to add boundary points. Need at least 3 points.</p>
    </div>
  );
}
