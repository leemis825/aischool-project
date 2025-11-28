import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import BubbleLayout from "../components/BubbleLayout.js";

export default function MessagePage() {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/listen");
  };

  const goToPhone = () => {
    navigate("/phone");
  };

  const goToSuccess = () => {
    navigate("/success");
  };
  return (
    <BubbleLayout
      //onClick={handleClick}
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
