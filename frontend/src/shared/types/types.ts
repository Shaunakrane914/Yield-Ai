export type LatLng = {
  lat: number;
  lng: number;
};

export type FarmPayload = {
  farm_name: string;
  boundary_coordinates: LatLng[];
};

export type FarmApiResponse = {
  status: string;
  message: string;
  farm_id: number;
  has_farm_setup?: boolean;
};

export type PredictionPayload = {
  district: string;
  crop: string;
  season?: string;
  variety?: string;
};
