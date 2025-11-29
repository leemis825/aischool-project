import { useNavigate, useLocation } from "react-router-dom";
import Layout from "../components/Layout.js";
import BubbleLayout from "../components/BubbleLayout.js";

export default function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // SummaryPage → navigate("/result", { state: { summary, engineResult } })
  const { engineResult } = (location.state || {}) as {
    summary?: string;
    engineResult?: {
      user_facing?: {
        answer_core?: string;
        next_action_guide?: string;
        main_message?: string;
      };
    };
  };

  const userFacing = engineResult?.user_facing || {};

  // 🔹 1순위: 핵심 답변(answer_core)
  // 🔹 2순위: next_action_guide
  // 🔹 3순위: main_message
  const contentText =
    userFacing.answer_core ||
    userFacing.next_action_guide ||
    userFacing.main_message ||
    "안내 문구를 불러오는 중 문제가 발생했습니다.";
  const handleClick = () => {
    navigate("/message");
  };

  return (
    <BubbleLayout
      onClick={handleClick}
      title="결과확인"
      image="src/assets/img1.png"
      topImage="src/assets/top2.png"
      content={contentText}
      content3="확인 후 화면 어디든 눌러주세요."
    ></BubbleLayout>
  );
}
