import { API_BASE_URL } from "./apiConfig";

export interface WeatherInfo {
  temp: number;
  max_temp: number;
  min_temp: number;
  feels_like: number;
  condition: string;
  location: string;
}

export interface LunarInfo {
  solar_date: string;
  lunar_date: string;
  seasonal_term: string;
}

export interface HeaderStatus {
  now_iso: string;
  date_display: string;
  weather: WeatherInfo | null;
  lunar: LunarInfo;
}

export async function getHeaderStatus(
  location: string = "Gwangju"
): Promise<HeaderStatus> {
  const url = `${API_BASE_URL}/api/status/header?location=${encodeURIComponent(
    location
  )}`;

  console.log("📡 calling headerStatus:", url);

  const res = await fetch(url);

  const contentType = res.headers.get("content-type") || "";
  const text = await res.text();
  console.log("🔍 raw response (first 200 chars):", text.slice(0, 200));

  if (!res.ok) {
    throw new Error(`Failed to fetch header status: ${res.status}`);
  }

  if (!contentType.includes("application/json")) {
    throw new Error(
      "API가 JSON이 아니라 HTML(아마 index.html)을 보내고 있습니다."
    );
  }

  return JSON.parse(text) as HeaderStatus;
}
