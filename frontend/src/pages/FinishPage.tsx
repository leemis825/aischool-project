import { useNavigate } from "react-router-dom";
import PlusLayout from "../components/PlusLayout.js";
import { useEffect } from "react";

export default function FinishPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/");
    }, 5000); // 10초

    return () => clearTimeout(timer); // cleanup
  }, [navigate]);
  return (
    <PlusLayout
      des=" "
      content={`궁금하신 내용이 있으면\n언제든 말씀해주세요.\n감사합니다.`}
      image="src/assets/img4.png"
    ></PlusLayout>
  );
}
