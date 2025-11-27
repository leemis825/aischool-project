import { API_BASE_URL } from "./apiConfig";

export async function analyzeMinwon(text: string): Promise<string> {
  const url = `${API_BASE_URL}/api/minwon/analyze`;

  console.log("📡 calling analyzeMinwon:", url);

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  const contentType = res.headers.get("content-type") || "";
  const raw = await res.text();
  console.log("🔍 analyzeMinwon raw response:", raw);

  if (!res.ok) {
    throw new Error(`민원 분석 요청 실패: ${res.status}`);
  }

  return res.json() as Promise<string>;
}
