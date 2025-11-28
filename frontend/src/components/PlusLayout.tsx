import type { ReactNode, CSSProperties } from "react";
import GwangjuLogo from "../assets/aischool.png";
interface PlusLayoutProps {
  content: string;
  des: string;
  children?: ReactNode;
  image?: string;
}

/* 바깥 전체 Wrapper */
const wrapperStyle: CSSProperties = {
  position: "relative",
  width: "100vw", // ← 브라우저 전체 너비
  height: "100vh",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  backgroundColor: "rgba(142, 209, 71, 0.77)",
  overflow: "hidden",
};

const whiteCardStyle: CSSProperties = {
  position: "absolute",
  top: "0",
  width: "100vw",
  height: "630px",
  background: "#FFFFFF",
  borderRadius: "0px 0px 100px 100px",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
};

/* 본문 내용 */
const contentStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  textAlign: "center",
  fontFamily: "KoddiUD OnGothic",
  fontWeight: 700,
  fontSize: "90px",
  color: "#000000",
  padding: "0 40px",
};

const desStyle: CSSProperties = {
  position: "absolute",
  marginLeft: "350px",
  marginTop: "50px",
  textAlign: "center",
  fontFamily: "KoddiUD OnGothic",
  fontWeight: 600,
  fontSize: "50px",
  color: "#000000",
  top: "635px",
};

const imageStyle: CSSProperties = {
  position: "absolute",
  bottom: "0",
  left: "0px",
};

const bottomAreaStyle: CSSProperties = {
  width: "100%",
  flex: 1, // 남는 영역 채우기
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-start",
  alignItems: "center",
  paddingTop: "40px",
  whiteSpace: "pre-line",
};
const childrenWrapperStyle: CSSProperties = {
  position: "absolute",
  top: "55%", // 화면 세로 기준 위치 (원하면 조절 가능)
  left: "50%",
  transform: "translate(-50%, -50%)", // 가운데 정렬
  width: "100%",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
};

const GwangjulogoStyle: CSSProperties = {
  position: "absolute",
  bottom: "6px",
  zIndex: 4,
  width: "300px",
  height: "auto",
  right: "20px",
};
function renderMultiline(content: string) {
  return content.split("\n").map((line, idx) => <div key={idx}>{line}</div>);
}

export default function PlusLayout({
  content,
  des,
  children,
  image,
}: PlusLayoutProps) {
  return (
    <div style={wrapperStyle}>
      <div style={whiteCardStyle}>
        {content && <div style={contentStyle}>{renderMultiline(content)}</div>}{" "}
      </div>
      <div style={childrenWrapperStyle}>{children}</div>
      <div style={bottomAreaStyle}>
        <div style={desStyle}>{des}</div>
        {image && <img src={image} alt="img decoration" style={imageStyle} />}
      </div>
      <img src={GwangjuLogo} alt="gwangju" style={GwangjulogoStyle} />
    </div>
  );
}
