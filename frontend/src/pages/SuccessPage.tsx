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
      content={`안내해 드린 내용을 참고하셔서 진행하시면 됩니다. 1999년생의 경우 노령연금은 만 65세, 조기노령연금은 만 60세부터 가능합니다`}
      content3="확인 후 화면 어디든 눌러주세요."
    ></BubbleLayout>
  );
}
