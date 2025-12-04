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
    engineResult?: {
      user_facing?: {
        answer_core?: string;
        next_action_guide?: string;
        main_message?: string;
        phone_suggestion?: string;
      };
    };
  };

  const userFacing =
    (engineResult?.user_facing || {}) as {
      answer_core?: string;
      next_action_guide?: string;
      main_message?: string;
      phone_suggestion?: string;
    };

  const contentText =
    userFacing.main_message ||
    userFacing.next_action_guide ||
    userFacing.answer_core ||
    "안내 문구를 불러오는 중 문제가 발생했습니다.";

  const detailText = "확인 후 화면 어디든 눌러주세요.";

  // 🔊 처리 안내 + 확인 안내 읽어주기 (한 번만)
  const spokenRef = useRef(false);
  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const text =
          contentText + " 확인 후 화면 아무 곳이나 눌러 주세요.";
        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);

        // 전역 오디오 매니저로 재생
        playTtsUrl(url);
      } catch (e) {
        console.error("ResultPage TTS 오류:", e);
      }
    };

    speak();

    // 컴포넌트 언마운트 / 라우팅 변경 시 오디오 정리
    return () => {
      stopTts();
    };
  }, [contentText]);

  const handleClick = () => {
    // 페이지 이동 전에 오디오 먼저 정지
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
      content={contentText}
      content3={detailText}
    ></BubbleLayout>
  );
}
