// frontend/src/services/gwangjuStateService.ts

import { API_BASE_URL } from "./apiConfig";

export interface WeatherInfo {
  temp: number;
  max_temp: number;
  min_temp: number;
  feels_like: number; // ✅ 백엔드에도 추가해 줄 예정
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
  lunar: LunarInfo | null; // ✅ 백엔드가 null 줄 수 있으므로
  holiday: string;
}

export async function getHeaderStatus(
  location: string = "Gwangju",
  test_date?: string
): Promise<HeaderStatus> {
  let url = `${API_BASE_URL}/api/status/header?location=${encodeURIComponent(
    location
  )}`;

  // ✅ 테스트용으로 날짜를 바꾸고 싶을 때만 사용
  if (test_date) {
    url += `&test_date=${encodeURIComponent(test_date)}`;
  }

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
