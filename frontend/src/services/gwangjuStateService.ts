// frontend/src/services/gwangjuStateService.ts

import { API_BASE_URL } from "./apiConfig";

// ----------------------------
// 백엔드에서 ClockPage가 기대하는 형태
// ----------------------------
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
  lunar: LunarInfo | null;
  holiday: string;
}

// ----------------------------
// /api/today-info 응답 타입
// ----------------------------
interface TodayInfoWeather {
  location: string;
  temp_c: number;
  temp_min_c: number;
  temp_max_c: number;
  feelslike_c: number;
  condition_text: string;
}

interface TodayInfoSeason {
  today: string;               // "2025-12-01"
  lunar_date: string | null;
  solar_term: string | null;
}

interface TodayInfoResponse {
  weather: TodayInfoWeather;
  season: TodayInfoSeason;
}

/**
 * 대기 화면 헤더 상태 조회
 * - 백엔드 /api/today-info 를 호출해서
 *   ClockPage가 쓰는 HeaderStatus 형태로 변환
 */
export async function getHeaderStatus(
  location: string = "Gwangju",
): Promise<HeaderStatus> {
  // 혹시 API_BASE_URL 끝에 / 가 있으면 제거
  const base = API_BASE_URL.replace(/\/$/, "");
  const url = `${base}/api/today-info?location=${encodeURIComponent(location)}`;

  console.log("[getHeaderStatus] Request URL:", url);

  const res = await fetch(url, { method: "GET" });

  const raw = await res.text();
  console.log(
    "[getHeaderStatus] raw response (first 200 chars):",
    raw.slice(0, 200),
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch today-info: ${res.status}`);
  }

  const data = JSON.parse(raw) as TodayInfoResponse;

  // 날짜 표시: YYYY-MM-DD → "2025년 12월 1일 (Mon)" 비슷하게
  const today = new Date(data.season.today);
  const y = today.getFullYear();
  const m = today.getMonth() + 1;
  const d = today.getDate();
  const dayNames = ["日", "月", "火", "水", "木", "金", "土"];
  const day = dayNames[today.getDay()];
  const date_display = `${y}년 ${m}월 ${d}일 (${day})`;

  const weather: WeatherInfo = {
    temp: Math.round(data.weather.temp_c),
    max_temp: Math.round(data.weather.temp_max_c),
    min_temp: Math.round(data.weather.temp_min_c),
    feels_like: Math.round(data.weather.feelslike_c),
    condition: data.weather.condition_text,
    location: data.weather.location,
  };

  const lunar: LunarInfo = {
    solar_date: data.season.today,
    lunar_date: data.season.lunar_date ?? "",
    seasonal_term: data.season.solar_term ?? "",
  };

  return {
    now_iso: today.toISOString(),
    date_display,
    weather,
    lunar,
    holiday: "",
  };
}
