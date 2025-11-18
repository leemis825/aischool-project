import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import PlusLayout from "../components/PlusLayout.js";

export default function SummaryPage() {
  return (
    <PlusLayout
      des="말씀하신 내용이 맞으신가요?"
      content={`요약 내용 뭐라무라루마ㅜㄹ아ㅜㄹ아ㅜㄹ눌우ㅐ`}
    >
      <div
        style={{
          background: "#FFF5C4",
          padding: "24px 32px",
          borderRadius: "24px",
          fontSize: "40px",
          lineHeight: 1.4,
          textAlign: "center",
          width: "90%",
        }}
      >
        예: 연금은 언제 받아?
        <br />집 앞 가로등에 불이 안 들어와.
      </div>
    </PlusLayout>
  );
}
