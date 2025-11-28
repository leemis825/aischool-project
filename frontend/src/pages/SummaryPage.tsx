import { useNavigate, useLocation } from "react-router-dom";
import BubbleLayout from "../components/BubbleLayout.js";

export default function SummaryPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // ListeningPage → navigate("/summary", { state: { summary: ... } })
  const { summary } = location.state || {};

  const goToReListen = () => {
    navigate("/relisten");
  };

  const goToResult = () => {
    navigate("/result", {
      state: {
        summary,
      },
    });
  };

  return (
    <BubbleLayout
      title="민원확인"
      topImage="src/assets/top2.png"
      content={summary ?? "요약 정보를 불러올 수 없습니다."}
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
          결과확인
        </button>
      </div>
    </BubbleLayout>
  );
}
