import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";

// 음력, 절기 api 연결 필요, 현재는 더미 데이터 사용

const wrapperStyle: CSSProperties = {
  width: "100vw",
  height: "100vh",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  overflow: "hidden",
};

const cardStyle: CSSProperties = {
  width: "100vw",
  height: "100vh",
  borderRadius: "24px",
  paddingTop: "100px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  cursor: "pointer",
  alignItems: "center",
};

const topRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  fontSize: "40px",
  fontFamily: "KoddiUD OnGothic",
  width: "100%",
  paddingRight: "120px",
  fontWeight: 800,
};

const dateBlockStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "4px",
};

const dateStyle: CSSProperties = {
  fontSize: "100px",
  fontWeight: 600,
  fontFamily: "KoddiUD OnGothic",
};

const lunarStyle: CSSProperties = {
  fontSize: "60px",
  fontWeight: 600,
  opacity: 0.7,
  fontFamily: "KoddiUD OnGothic",
  alignSelf: "flex-end",
};

const timeStyle: CSSProperties = {
  fontSize: "350px",
  fontWeight: 700,
  letterSpacing: "0.07em",
  fontFamily: "Lab",
  marginTop: " -50px",
  marginBottom: "50px",
};

function formatDate(date: Date) {
  const y = date.getFullYear();
  const m = date.getMonth() + 1;
  const d = date.getDate();
  const dayNames = ["日", "月", "火", "水", "木", "金", "土"];
  const day = dayNames[date.getDay()];
  return `${y}년 ${m}월 ${d}일 (${day})`;
}

function formatTime(date: Date) {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh} : ${mm}`;
}

export default function ClockPage() {
  const [now, setNow] = useState(new Date());
  const navigate = useNavigate();

  // 🔥 1초마다 시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // 더미 데이터
  const solarTerm = "소설(小雪)";
  const maxTemp = 18;
  const minTemp = 5;
  const weatherIcon = "☀";
  const lunarText = "음력 10월 12일";

  const handleClick = () => {
    navigate("/complaint");
  };

  return (
    <div style={wrapperStyle} onClick={handleClick}>
      <div style={cardStyle}>
        {/* 절기 + 날씨 */}
        <div style={topRowStyle}>
          <span>
            {solarTerm} · {weatherIcon} {maxTemp}℃ / {minTemp}℃
          </span>
        </div>

        {/* 날짜 + 음력 */}
        <div style={dateBlockStyle}>
          <div style={dateStyle}>{formatDate(now)}</div>
          <div style={lunarStyle}>{lunarText}</div>
        </div>

        {/* 시계 */}
        <div style={timeStyle}>{formatTime(now)}</div>
      </div>
    </div>
  );
}
