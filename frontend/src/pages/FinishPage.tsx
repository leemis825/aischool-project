import { useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import PlusLayout from "../components/PlusLayout.js";
import { requestTts } from "../services/ttsService";

export default function FinishPage() {
  const navigate = useNavigate();
  const spokenRef = useRef(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const speakAndSchedule = async () => {
      if (!spokenRef.current) {
        spokenRef.current = true;
        try {
          const text =
            "필요하시면 또 불러 주세요. 화면은 자동으로 처음 화면으로 넘어가요. 또 봬요.";
          const blob = await requestTts(text);
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);

          audio.onended = () => URL.revokeObjectURL(url);
          audio.onerror = () => URL.revokeObjectURL(url);

          audio.play();
        } catch (e) {
          console.error("FinishPage TTS 오류:", e);
        }
      }

      // 🔁 10초 뒤 처음 화면으로 이동
      timer = setTimeout(() => {
        navigate("/");
      }, 10000);
    };

    speakAndSchedule();

    return () => {
      if (timer) clearTimeout(timer);
    };
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
