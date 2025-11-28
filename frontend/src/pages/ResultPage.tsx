import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import BubbleLayout from "../components/BubbleLayout.js";

export default function ResultPage() {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate("/message");
  };
  return (
    <BubbleLayout
      onClick={handleClick}
      title="결과확인"
      image="src/assets/img1.png"
      topImage="src/assets/top2.png"
      content="AI 대답 내보내기"
      content3="확인 후 화면 어디든 눌러주세요."
    ></BubbleLayout>
  );
}
