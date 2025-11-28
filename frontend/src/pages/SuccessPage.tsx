import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import BubbleLayout from "../components/BubbleLayout.js";
import { useEffect } from "react";

export default function SuccessPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/finish"); //
    }, 5000); // 10초

    return () => clearTimeout(timer); // cleanup
  }, [navigate]);
  return (
    <BubbleLayout
      //onClick={handleClick}
      title="접수완료"
      image="src/assets/img2.png"
      topImage="src/assets/top2.png"
      content={`[무슨무슨기관] 으로\n민원이\n접수되었습니다.`}
    ></BubbleLayout>
  );
}
