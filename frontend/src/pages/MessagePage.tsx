// src/pages/MessagePage.tsx
import { useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import BubbleLayout from "../components/BubbleLayout.js";
import { requestTts } from "../services/ttsService";
import { playTtsUrl, stopTts } from "../services/audioManager";

export default function MessagePage() {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/listen");
  };

  const goToPhone = () => {
    stopTts(); // 🔊 재생 중이면 끊고 이동
    navigate("/phone");
  };

  const goToSuccess = () => {
    stopTts();
    navigate("/success");
  };

  // 🔊 이 페이지에서 고정 멘트를 한 번만 읽어주기 위한 ref
  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const text =
          "민원 처리 내용을 문자로 받아보시겠어요? " +
          "네 버튼을 누르시면 연락 받으실 전화번호를 입력하는 화면으로 이동합니다. " +
          "아니오 버튼을 누르시면 바로 접수 완료 화면으로 이동합니다.";
        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);

        // 🔊 전역 오디오 매니저로 재생
        playTtsUrl(url);
      } catch (e) {
        console.error("MessagePage TTS 오류:", e);
      }
    };

    speak();

    // 🔥 페이지 떠날 때 오디오 정리
    return () => {
      stopTts();
    };
  }, []);

  return (
    <BubbleLayout
      // onClick={handleClick}
      title="문자안내"
      image="src/assets/img2.png"
      topImage="src/assets/top2.png"
      content={`민원처리 내용을 문자로\n받아보시겠어요?`}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "24px",
          width: "100%",
          marginTop: "20px",
        }}
      >
        <button
          onClick={goToPhone}
          style={{
            padding: "20px 40px",
            fontSize: "32px",
            borderRadius: "20px",
            background: "#F0F0F0",
            cursor: "pointer",
          }}
        >
          네
        </button>

        <button
          onClick={goToSuccess}
          style={{
            padding: "20px 40px",
            fontSize: "32px",
            borderRadius: "20px",
            background: "#FBDA05",
            cursor: "pointer",
          }}
        >
          아니오
        </button>
      </div>
    </BubbleLayout>
  );
}
