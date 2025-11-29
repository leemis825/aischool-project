import { useNavigate } from "react-router-dom";
import PlusLayout from "../components/PlusLayout.js";
import { useEffect } from "react";

export default function FinishPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/");
    }, 10000); // 10초

    return () => clearTimeout(timer); // cleanup
  }, [navigate]);
  return (
    <PlusLayout
      des=" "
      content={`필요하시면 또 불러주세요\n감사합니다`}
      image="src/assets/img4.png"
      children="시간이 지나면 자동으로 처음 화면으로 돌아갑니다."
    ></PlusLayout>
  );
}
