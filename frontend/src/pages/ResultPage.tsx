// src/pages/ResultPage.tsx
import { useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef } from "react";
import BubbleLayout from "../components/BubbleLayout.js";

import { requestTts } from "../services/ttsService";
import { playTtsUrl, stopTts } from "../services/audioManager";

export default function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { engineResult } = (location.state || {}) as {
    engineResult?: any;
  };

  const userFacing = (engineResult?.user_facing || {}) as {
    result_text?: string;
    result_tts?: string;
    next_action_guide?: string;
  };

  // ------------------------------------------
  // 📌 화면용 텍스트 (공감 멘트 제외, 짧은 안내)
  //   → minwon_engine.user_facing.result_text 우선 사용
  // ------------------------------------------
  const displayResultText: string =
    userFacing.result_text ||
    userFacing.next_action_guide ||
    "담당 부서에서 현장을 확인해 조치할 예정입니다.";

  // ------------------------------------------
  // 🔊 음성용 텍스트 (공감 + 조치 계획 포함)
  //   → 백엔드에서 만든 result_tts 가 있으면 그걸 그대로 사용
  // ------------------------------------------
  const ttsText: string =
    userFacing.result_tts ||
    `${displayResultText} 확인 후 화면 아무 곳이나 눌러 주세요.`;

  // ------------------------------------------
  // 🔊 컴포넌트 첫 진입 시 음성 1회 재생
  // ------------------------------------------
  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const blob = await requestTts(ttsText);
        const url = URL.createObjectURL(blob);
        playTtsUrl(url);
      } catch (err) {
        console.error("ResultPage TTS 오류:", err);
      }
    };

    speak();

    return () => {
      stopTts();
    };
  }, [ttsText]);

  // ------------------------------------------
  // 🔘 화면 클릭 → 문자 안내 페이지로 이동
  // ------------------------------------------
  const handleClick = () => {
    stopTts();
    navigate("/message", {
      state: { engineResult },
    });
  };

  return (
    <BubbleLayout
      onClick={handleClick}
      title="결과확인"
      image="src/assets/img1.png"
      topImage="src/assets/top2.png"
      content={displayResultText} // 화면에는 짧은 결과 안내만
      content3="확인 후 화면 어디든 눌러주세요."
    />
  );
}
