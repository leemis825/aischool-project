import { API_BASE_URL } from "./apiConfig";

/**
 * /api/session/start
 *
 * 민원 텍스트 기반 세션을 하나 생성하고
 * session_id(string)를 반환하는 API
 */
export async function startMinwonSession(): Promise<string> {
  const url = `${API_BASE_URL}/api/session/start`;

  console.log("📡 calling session/start:", url);

  const res = await fetch(url, {
    method: "POST",
  });

  const raw = await res.text();
  console.log("🔍 /api/session/start raw:", raw);

  if (!res.ok) {
    throw new Error(`세션 생성 실패: ${res.status}`);
  }

  // Swagger에서 200 응답이 "string" (즉 JSON 문자열)이라고 되어 있으므로
  // JSON.parse("...") 형태
  try {
    return JSON.parse(raw) as string;
  } catch {
    // 혹시 그냥 텍스트면 그대로 사용
    return raw;
  }
}
