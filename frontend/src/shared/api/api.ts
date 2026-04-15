import type { FarmApiResponse, FarmPayload, PredictionPayload } from "@/shared/types/types";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "http://localhost:8000";

async function parseJson<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    throw new Error(text || "Server did not return JSON");
  }
  return response.json() as Promise<T>;
}

export async function saveFarm(payload: FarmPayload): Promise<FarmApiResponse> {
  const response = await fetch(`${API_BASE_URL}/my-farm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  const data = await parseJson<FarmApiResponse & { detail?: string }>(response);
  if (!response.ok) {
    throw new Error(data.detail || data.message || "Unable to save farm");
  }
  return data;
}

export async function getMyFarmState(): Promise<{ has_farm: boolean }> {
  const response = await fetch(`${API_BASE_URL}/my-farm`, { credentials: "include" });
  const data = await parseJson<{ has_farm?: boolean; detail?: string }>(response);
  if (!response.ok) {
    throw new Error(data.detail || "Unable to fetch farm state");
  }
  return { has_farm: Boolean(data.has_farm) };
}

export async function predictYield(payload: PredictionPayload): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/predict-advanced`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  const data = await parseJson<Record<string, unknown> & { detail?: string }>(response);
  if (!response.ok) {
    throw new Error(data.detail || "Prediction request failed");
  }
  return data;
}

export { API_BASE_URL };
