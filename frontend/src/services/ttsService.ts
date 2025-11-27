import { API_BASE_URL } from "./apiConfig";

/**
 * /tts
 * 텍스트를 받아 네이버 CLOVA Voice API를 통해
 * MP3 음성으로 변환한 결과를 반환받는 함수.
 * 프론트에서는 Blob으로 받아서 <audio> 재생 등으로 사용.
 */
export async function requestTts(text: string): Promise<Blob> {
  const url = `${API_BASE_URL}/tts`;

  console.log("📡 calling TTS:", url, "text:", text);

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    console.error("❌ TTS error:", res.status, errText);
    throw new Error(`TTS 요청 실패: ${res.status}`);
  }

  // 🔥 여기서는 MP3 바이너리라고 가정하고 blob()으로 받는다
  const blob = await res.blob();
  return blob;
}
