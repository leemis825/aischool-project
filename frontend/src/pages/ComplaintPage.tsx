import { useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import Layout from "../components/Layout.js";
import { requestTts } from "../services/ttsService";

export default function ComplaintPage() {
  const navigate = useNavigate();

  // 🔒 StrictMode에서 useEffect 두 번 실행되는 것 방지용
  const didPlayRef = useRef(false);

  useEffect(() => {
    if (didPlayRef.current) return;   // 이미 한 번 실행했으면 그냥 종료
    didPlayRef.current = true;

    const speakIntro = async () => {
      try {
        const text =
          "안녕하세요. 화면 어디든 터치 후 민원을 말씀해 주세요.";
        console.log("🎧 calling TTS intro:", text);

        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        audio.onended = () => {
          URL.revokeObjectURL(url);
        };

        audio.play();
      } catch (e) {
        console.error("초기 안내 음성 재생 중 오류:", e);
      }
    };

    speakIntro();
  }, []);

  const handleClick = () => {
    navigate("/listen");
  };

  return (
    <Layout
      onClick={handleClick}
      title="민원접수"
      content={`버튼 터치 후 
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
