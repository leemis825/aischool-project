const baseUrl = import.meta.env.VITE_API_BASE_URL;

console.log("🔧 VITE_API_BASE_URL =", baseUrl);

if (!baseUrl) {
  console.warn("⚠️ VITE_API_BASE_URL가 설정되지 않았습니다.");
}

export const API_BASE_URL = baseUrl ?? "http://localhost:8000";
