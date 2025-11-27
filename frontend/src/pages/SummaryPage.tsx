import { useNavigate } from "react-router-dom";
import PlusLayout from "../components/PlusLayout.js";
import BubbleLayout2 from "../components/BubbleLayout2.js";

export default function SummaryPage() {
  const navigate = useNavigate();

  const goToReListen = () => {
    navigate("/relisten");
  };

  const goToResult = () => {
    navigate("/result");
  };
  return (
    <BubbleLayout2
      title="민원요약"
      content={`요약 내용 뭐라무라ㅇㅇㅇㅇㅇㅇㅇㄴㄴㄴㄴㄴㄴ루마ㅜㅇㄹㄴㄹ아ㅜㄹ눌우ㅐ`}
      content2="요약 내용이 맞으시면 [예] 아니면 [재질문]을 눌러주세요"
      image="src/assets/img5.png"
    >
      {/* 이 부분은 추후 삭제 예정 */}
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
    </BubbleLayout2>
  );
}
