// src/pages/SummaryPage.tsx
import { useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef } from "react";
import BubbleLayout from "../components/BubbleLayout.js";
import { requestTts } from "../services/ttsService";

export default function SummaryPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { summary, engineResult } = (location.state || {}) as {
    summary?: string;
    engineResult?: any;
  };
  // 🔥 engineResult 를 sessionStorage 에 백업 (안전장치)
  useEffect(() => {
    if (engineResult) {
      sessionStorage.setItem(
        "lastEngineResult",
        JSON.stringify(engineResult)
    );
  }
}, [engineResult]);


  // 🔹 백엔드에서 온 값들 꺼내기 (없으면 undefined)
  const staffSummary: string | undefined = engineResult?.staff_payload?.summary;
  const citizenRequest: string | undefined =
    engineResult?.staff_payload?.citizen_request;
  const userFacing = (engineResult?.user_facing || {}) as {
    answer_core?: string;
  };
  const answerCore: string | undefined = userFacing.answer_core;

  // 🔎 화면에 보여줄 요약 문장 선택
  const displaySummary: string =
    citizenRequest ||
    answerCore ||
    staffSummary ||
    summary ||
    "요약 정보를 불러올 수 없습니다.";

  // 🔊 요약 + 버튼 안내 읽어주기 (한 번만)
  const spokenRef = useRef(false);
  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const text =
          displaySummary +
          " 요약 내용이 맞으시면 예 버튼을 눌러 주세요. " +
          "다시 말씀하고 싶으시면 재질문 버튼을 눌러 주세요.";
        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        audio.onended = () => URL.revokeObjectURL(url);
        audio.onerror = () => URL.revokeObjectURL(url);

        audio.play();
      } catch (e) {
        console.error("SummaryPage TTS 오류:", e);
      }
    };

    speak();
  }, [displaySummary]);

  const goToReListen = () => {
    navigate("/relisten");
  };

  const goToResult = () => {
    // engineResult가 없어도 일단 이동은 되게
    navigate("/result", {
      state: {
        summary: displaySummary,
        engineResult: engineResult || null,
      },
    });
  };

  return (
    <BubbleLayout
      title="민원확인"
      topImage="src/assets/top2.png"
      content={displaySummary}
      content2="요약 내용이 맞으시면 [예] 아니면 [재질문]을 눌러주세요."
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
      </div>
    </BubbleLayout>
  );
}
