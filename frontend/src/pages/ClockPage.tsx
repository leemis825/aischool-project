import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import Logo from "../assets/logo2.png";
import Clock from "../assets/img0.png";
import {
  getHeaderStatus,
  type HeaderStatus,
} from "../services/gwangjuStateService";

const topRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  fontSize: "40px",
  fontFamily: "surround",
  width: "100%",
  paddingRight: "160px",
  fontWeight: 800,
  marginTop: "-90px",
};

const dateBlockStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "4px",
};

const dateStyle: CSSProperties = {
  fontSize: "90px",
  fontWeight: 600,
  fontFamily: "surround",
};

const lunarStyle: CSSProperties = {
  fontSize: "50px",
  fontWeight: 600,
  opacity: 0.7,
  fontFamily: "surround",
  alignSelf: "flex-end",
};

const timeStyle: CSSProperties = {
  fontSize: "250px",
  fontWeight: 700,
  letterSpacing: "0.07em",
  fontFamily: "Lab",
  marginTop: " -50px",
  marginBottom: "50px",
};

const screenWrapperStyle: CSSProperties = {
  width: "100vw",
  height: "100%",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  background: "rgba(142, 209, 71, 0.77)",
  position: "relative",
};
const floatingClockStyle: CSSProperties = {
  position: "absolute",
  width: "60px",
  height: "60px",
  zIndex: 2,
};

const whiteCardStyle: CSSProperties = {
  position: "absolute",
  width: "95vw",
  height: "520px",
  background: "#FFFFFF",
  borderRadius: "100px",
  top: "90px",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  paddingTop: "160px", // content와 topWhite 사이 공간
  overflow: "hidden",
  borderBlockEnd: "8px solid #668b5a",
  borderRight: "8px solid #668b5a",
};

const logoStyle: CSSProperties = {
  position: "absolute",
  top: "20px",
  right: "20px",
  width: "180px",
  height: "auto",
  zIndex: 4,
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
  const [headerStatus, setHeaderStatus] = useState<HeaderStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setError(null);
        const data = await getHeaderStatus("Gwangju");
        setHeaderStatus(data);
      } catch (e) {
        console.error(e);
        setError("상태 정보를 불러오는 중 오류가 발생했습니다.");
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 60_000);
    return () => clearInterval(interval);
  }, []);

  const handleClick = () => {
    navigate("/complaint");
  };

  // ✅ 응답 도착 여부
  const isLoaded = !!headerStatus;

  // ✅ 날짜
  const dateDisplay = formatDate(now);

  // ✅ 절기 / 음력 (빈 문자열이면 '정보 없음'으로)
  const solarTerm =
    headerStatus && headerStatus.lunar.seasonal_term
      ? headerStatus.lunar.seasonal_term
      : isLoaded
      ? "절기 정보 없음"
      : "절기 정보를 불러오는 중...";

  const lunarText =
    headerStatus && headerStatus.lunar.lunar_date
      ? headerStatus.lunar.lunar_date
      : isLoaded
      ? "음력 정보 없음"
      : "음력 정보를 불러오는 중...";

  // ✅ 날씨 텍스트
  let weatherText: string;
  if (!isLoaded) {
    weatherText = "날씨 정보를 불러오는 중...";
  } else if (!headerStatus?.weather) {
    weatherText = "날씨 정보 없음";
  } else {
    const { temp, feels_like, condition } = headerStatus.weather;
    weatherText = `${condition} ${temp}℃ / ${feels_like}℃`;
  }

  return (
    <div style={screenWrapperStyle} onClick={handleClick}>
      <img src={Logo} alt="head" style={logoStyle} />

      <img
        src={Clock}
        alt="floating"
        className="float-free-wide"
        style={floatingClockStyle}
      />
      <div style={whiteCardStyle}>
        <div style={topRowStyle}>
          <span>
            {solarTerm} · {weatherText}
          </span>
        </div>

        {error && (
          <div
            style={{
              color: "red",
              fontSize: "20px",
              marginTop: "16px",
              textAlign: "center",
            }}
          >
            {error}
          </div>
        )}

        {/* 날짜 + 음력 */}
        <div style={dateBlockStyle}>
          <div style={dateStyle}>{dateDisplay}</div>
          <div style={lunarStyle}>{lunarText}</div>
        </div>

        {/* 시계 */}
        <div style={timeStyle}>{formatTime(now)}</div>
      </div>
    </div>
  );
}
