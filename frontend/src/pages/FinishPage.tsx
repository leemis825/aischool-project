// src/pages/FinishPage.tsx
import { useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import PlusLayout from "../components/PlusLayout.js";
import { requestTts } from "../services/ttsService";
import { playTtsUrl, stopTts } from "../services/audioManager";

export default function FinishPage() {
  const navigate = useNavigate();

  // 🔊 이 페이지에서 음성을 한 번만 재생하기 위한 플래그
  const spokenRef = useRef(false);
  // ⏱ setTimeout ID 저장용 (브라우저에서는 number)
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const speakAndAutoMove = async () => {
      // 음성은 한 번만 재생
      if (!spokenRef.current) {
        spokenRef.current = true;

        try {
          const text =
            "필요하시면 또 불러 주세요. 화면은 자동으로 처음 화면으로 넘어가요. 또 봬요.";
          const blob = await requestTts(text);
          const url = URL.createObjectURL(blob);

          // 전역 오디오 매니저로 재생 (이전 TTS 자동 정리)
          playTtsUrl(url);
        } catch (err) {
          console.error("FinishPage TTS 오류:", err);
        }
      }

      // 10초 후 첫 화면으로 자동 이동
      timerRef.current = window.setTimeout(() => {
        // 이동 전에 음성 먼저 정지
        stopTts();
        navigate("/");
      }, 10000);
    };

    speakAndAutoMove();

    // 🔥 언마운트/페이지 이동 시 정리
    return () => {
      stopTts();
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [navigate]);

  return (
    <PlusLayout
      des=" "
      content={`필요하시면 또 불러주세요\n감사합니다`}
      image="src/assets/img4.png"
      children="시간이 지나면 자동으로 처음 화면으로 돌아갑니다."
    />
  );
}
