import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";

export default function ComplaintPage() {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate("/listen");
  };
  return (
    <Layout
      onClick={handleClick}
      title="민원접수"
      content={`화면을 누르고
        민원을 말씀해주세요`}
      topImage="src/assets/top2.png"
      image="src/assets/img6.png"
    >
      <div
        style={{
          background: "#CBF3C7",
          padding: "24px 32px",
          fontSize: "40px",
          lineHeight: 1.4,
          textAlign: "center",
          width: "55%",
          borderRadius: "90px",
        }}
      >
        예: 연금은 언제 받아?
        <br />집 앞 가로등에 불이 안 들어와.
      </div>
    </Layout>
  );
}
