// src/pages/SummaryPage.tsx
import { useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef } from "react";
import BubbleLayout from "../components/BubbleLayout.js";

import { playTtsUrl, stopTts } from "../services/audioManager";
import { requestTts } from "../services/ttsService";

export default function SummaryPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // ListeningPage 에서 넘겨주는 값들
  const { summary, engineResult } = (location.state || {}) as {
    summary?: string; // 옵션: 백엔드 staff_summary 직접 전달
    engineResult?: any; // 민원 엔진 전체 결과
  };

  // ----------------------------
  // 엔진에서 내려준 user_facing / staff_payload
  // ----------------------------
  const userFacing = engineResult?.user_facing || {};
  const staffPayload = engineResult?.staff_payload || {};

  // 화면에 보여줄 한 줄 요약
  const summaryText: string =
    // 1) 엔진에서 summary_text 제공하면 그걸 우선
    userFacing.summary_text ||
    // 2) ListeningPage 가 따로 넘긴 summary
    summary ||
    // 3) 담당자용 citizen_request (간단한 한 줄 요청)
    staffPayload.citizen_request ||
    // 4) 담당자용 summary (조금 길 수 있음)
    staffPayload.summary ||
    "요약 정보를 불러올 수 없습니다.";

  // 음성으로 읽어줄 문장 (엔진에 있으면 그대로 사용)
  const summaryTts: string =
    userFacing.summary_tts ||
    `말씀해 주신 내용은 ${summaryText} 내용이 맞으실까요?`;

  // 화면에 실제로 표시할 값
  const displaySummary = summaryText;

  // ----------------------------
  // 🔥 sessionStorage 백업
  // ----------------------------
  useEffect(() => {
    if (engineResult) {
      sessionStorage.setItem("lastEngineResult", JSON.stringify(engineResult));
    }
  }, [engineResult]);

  // ----------------------------
  // 🔊 SummaryPage 들어올 때 1회 음성 재생
  // ----------------------------
  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const ttsText =
          summaryTts +
          " 요약 내용이 맞으시면 예 버튼을 눌러 주세요. 다시 말씀하고 싶으시면 재질문 버튼을 눌러 주세요.";

        const blob = await requestTts(ttsText);
        const url = URL.createObjectURL(blob);

        playTtsUrl(url); // 🔥 audioManager 사용!
      } catch (err) {
        console.error("SummaryPage TTS 오류:", err);
      }
    };

    speak();

    return () => {
      stopTts();
    };
  }, [summaryTts]);

  // ----------------------------
  // 버튼 동작
  // ----------------------------
  const goToReListen = () => {
    stopTts(); // 🔥 버튼 눌러 페이지 이동할 때도 확실히 정지
    navigate("/listen");
  };

  const goToResult = () => {
    stopTts();
    navigate("/result", {
      state: {
        engineResult,
      },
    });
  };

  return (
    <BubbleLayout
      title="민원확인"
      topImage="src/assets/top2.png"
      content={displaySummary}
      content2="요약 내용이 맞으시면 [예], 아니면 [재질문]을 눌러주세요."
      image="src/assets/img5.png"
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
          onClick={goToResult}
          style={{
            padding: "20px 40px",
            fontSize: "32px",
            borderRadius: "20px",
            background: "#FBDA05",
            cursor: "pointer",
          }}
        >
          예
        </button>
        <button
          onClick={goToReListen}
          style={{
            padding: "20px 40px",
            fontSize: "32px",
            borderRadius: "20px",
            background: "#F0F0F0",
            cursor: "pointer",
          }}
        >
          재질문
        </button>
      </div>
    </BubbleLayout>
  );
}
