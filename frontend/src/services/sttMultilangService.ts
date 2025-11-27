import { API_BASE_URL } from "./apiConfig";

export async function sttMultilang(
  audioFile: File | Blob,
  filename: string = "record.webm"
): Promise<string> {
  const url = `${API_BASE_URL}/stt/multilang`;

  const formData = new FormData();
  formData.append("audio", audioFile, (audioFile as File).name ?? filename);

  console.log("📡 calling STT Multilang:", url);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  const raw = await res.text();
  console.log("🔍 /stt/multilang raw response:", raw);

  if (!res.ok) {
    throw new Error(`STT 다국어 민원 엔진 요청 실패: ${res.status}`);
  }

  // Swagger에서 200 응답 schema가 "string" 이라고 되어 있어서
  // JSON 문자열("...")일 수도 있고, 그냥 text일 수도 있음 → 둘 다 대비
  try {
    return JSON.parse(raw) as string;
  } catch {
    return raw;
  }
}
