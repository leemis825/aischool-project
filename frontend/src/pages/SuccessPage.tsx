import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import BubbleLayout from "../components/BubbleLayout.js";
import { useEffect } from "react";

export default function SuccessPage() {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate("/finish");
  };

  return (
    <BubbleLayout
      onClick={handleClick}
      title="접수완료"
      image="src/assets/img2.png"
      topImage="src/assets/top2.png"
      content={`[무슨무슨기관] 으로\n민원이\n접수되었습니다.`}
      content3="확인 후 화면 어디든 눌러주세요."
    ></BubbleLayout>
  );
}
