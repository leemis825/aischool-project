import { API_BASE_URL } from "./apiConfig";

/**
 * /stt
 * 프론트에서 녹음한 음성 파일(webm/mp3 등)을 업로드하면
 * 1) OpenAI Whisper로 STT (ko)
 * 2) 변환된 텍스트를 민원 엔진에 넣어 분류/요약
 * 까지 처리한 결과를 문자열로 반환하는 API
 *
 * FastAPI 쪽 시그니처가 대략:
 *   async def stt_and_minwon(audio: UploadFile = File(...))
 * 이런 형태일 거라서, 필드 이름을 "audio"로 맞춤.
 */

export async function sttAndMinwon(
  audioFile: File | Blob,
  filename: string = "record.webm"
): Promise<string> {
  const url = `${API_BASE_URL}/stt`;
  const formData = new FormData();
  // FastAPI UploadFile 파라미터 이름에 맞춰야 함 (audio)
  formData.append("audio", audioFile, (audioFile as File).name ?? filename);

  console.log("📡 calling STT+Minwon:", url);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  const raw = await res.text();
  console.log("🔍 /stt raw response:", raw);

  if (!res.ok) {
    throw new Error(`STT+민원 엔진 요청 실패: ${res.status}`);
  }

  // FastAPI schema 에서 200 응답이 "string" 이라고 되어 있어서,
  // JSON 문자열("...")일 수도 있고, 그냥 text일 수도 있어서 둘 다 대비
  try {
    return JSON.parse(raw) as string; // "요약문" 형태
  } catch {
    return raw; // 그냥 텍스트면 그대로 반환
  }
}
