// src/utils/playTts.ts

/**
 * 네이버 TTS 백엔드(/tts)를 호출해서
 * 전달받은 텍스트를 음성으로 재생해 주는 유틸 함수.
 *
 * 사용 예:
 *   await playTts("안녕하세요. 화면을 눌러 주세요.");
 *   await playTts("조금 더 천천히 말하기", { speed: -3 });
 */

export async function playTts(
  text: string,
  options?: {
    speed?: number;   // -5 ~ 5 (기본: -2, 조금 느리게)
    speaker?: string; // 예: "nara", "jinho"
  }
) {
  const trimmed = (text || "").trim();
  if (!trimmed) return;

  try {
    const body = {
      text: trimmed,
      speaker: options?.speaker ?? "nara",
      speed: options?.speed ?? -2,
    };

    const res = await fetch("http://localhost:8000/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      console.error("[playTts] TTS 호출 실패:", res.status, await res.text());
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  } catch (err) {
    console.error("[playTts] 재생 중 오류:", err);
  }
}
