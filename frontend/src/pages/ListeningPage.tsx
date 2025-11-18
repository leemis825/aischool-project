import { Navigate, useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
export default function ListeningPage() {
  const navigate = useNavigate();
  const handleClick = () => {
    navigate("/summary");
  };
  return (
    <Layout
      title="민원확인"
      content={`민원을 듣고 있어요`}
      headerImage="src/assets/duck1.png"
      onClick={handleClick}
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
      ></div>
    </Layout>
  );
}
