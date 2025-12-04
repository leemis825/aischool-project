import { useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef } from "react";
import BubbleLayout from "../components/BubbleLayout.js";
import { requestTts } from "../services/ttsService";
import { playTtsUrl, stopTts } from "../services/audioManager";

// ------------------------------------------
// 🔹 Location 또는 sessionStorage 어디서든 engineResult 가져오기
// ------------------------------------------
function getEngineResultFromAnywhere(locationState: any): any | undefined {
  if (locationState?.engineResult) return locationState.engineResult;

  try {
    const saved = sessionStorage.getItem("lastEngineResult");
    if (!saved) return undefined;
    return JSON.parse(saved);
  } catch {
    return undefined;
  }
}

// ------------------------------------------
// 🔹 부서 이름 결정 로직
// ------------------------------------------
function getDeptName(engineResult: any): string {
  if (!engineResult) return "담당 기관";

  // 1️⃣ 백엔드에서 직접 준 부서명이 있으면 최우선 사용
  const directDept =
    engineResult.dept_name ||
    engineResult.department_name ||
    engineResult.dept?.name;
  if (directDept) return String(directDept);

  // 2️⃣ staff_payload.category 기준 우선 매핑
  const categoryRaw: string | undefined =
    engineResult.staff_payload?.category ??
    engineResult.staff_payload?.category_main;
  const categoryKey = categoryRaw ? categoryRaw.split("-")[0] : "";

  const categoryMap: Record<string, string> = {
    도로: "도로 담당 부서",
    시설물: "시설물 담당 부서",
    "연금/복지": "연금·복지 담당 부서",
    심리지원: "심리상담 지원 부서",
    생활민원: "생활민원 담당 부서",
    기타: "민원실",
  };

  if (categoryKey && categoryMap[categoryKey]) {
    return categoryMap[categoryKey];
  }

  // 3️⃣ 그래도 안 나오면 minwon_type 기준으로 한 번 더 매핑
  const minwonType: string | undefined = engineResult.minwon_type;
  if (minwonType && categoryMap[minwonType]) {
    return categoryMap[minwonType];
  }

  // 4️⃣ 최종 fallback
  return "담당 기관";
}

// ------------------------------------------
//               COMPONENT
// ------------------------------------------
export default function SuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const engineResult = getEngineResultFromAnywhere(location.state || {});
  console.log("🔥 SuccessPage engineResult:", engineResult);

  const deptName = getDeptName(engineResult);
  console.log("🔥 SuccessPage deptName:", deptName);

  const spokenRef = useRef(false);

  useEffect(() => {
    if (spokenRef.current) return;
    spokenRef.current = true;

    const speak = async () => {
      try {
        const text = `${deptName}으로 민원이 접수되었습니다. 확인 후 화면 아무 곳이나 눌러 주세요.`;
        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);

        // 🔊 전역 오디오 매니저로 재생
        playTtsUrl(url);
      } catch (e) {
        console.error("SuccessPage TTS 오류:", e);
      }
    };

    speak();

    // 언마운트 시 오디오 정리
    return () => {
      stopTts();
    };
  }, [deptName]);

  const handleClick = () => {
    // 화면 이동 전에 오디오 먼저 정지
    stopTts();
    navigate("/finish");
  };

  return (
    <BubbleLayout
      onClick={handleClick}
      title="접수완료"
      image="src/assets/img2.png"
      topImage="src/assets/top2.png"
      content={`[${deptName}] 으로\n민원이\n접수되었습니다.`}
      content3="확인 후 화면 어디든 눌러주세요."
    />
  );
}
