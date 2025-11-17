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
      title="민원확인"
      content={`화면을 누르고
        민원을 말씀해주세요`}
      headerImage="src/assets/duck1.png"
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
    </Layout>
  );
}
