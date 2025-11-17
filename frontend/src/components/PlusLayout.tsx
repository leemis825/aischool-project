import type { ReactNode, CSSProperties } from "react";

interface PlusLayoutProps {
  content: string;
  des: string;
  children?: ReactNode;
}

/* 바깥 전체 Wrapper */
const wrapperStyle: CSSProperties = {
  position: "relative",
  width: "100vw", // ← 브라우저 전체 너비
  height: "100vh",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  background: "#FBDA05",
  overflow: "hidden",
};

/* 하단 큰 흰색 카드 */
const whiteCardStyle: CSSProperties = {
  position: "absolute",
  top: "0",
  width: "100vw",
  height: "600px",
  background: "#FFFFFF",
  borderRadius: "0px 0px 150px 150px",
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
  right: 0,
  padding: "0 20px",
  textAlign: "center",
  fontFamily: "KoddiUD OnGothic",
  fontWeight: 600,
  fontSize: "40px",
  color: "#000000",
  top: "650px",
};

const bottomAreaStyle: CSSProperties = {
  width: "100%",
  flex: 1, // 남는 영역 채우기
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-start",
  alignItems: "center",
  paddingTop: "40px",
};

export default function PlusLayout({
  content,
  des,
  children,
}: PlusLayoutProps) {
  return (
    <div style={wrapperStyle}>
      <div style={whiteCardStyle}>
        <div style={contentStyle}> {content}</div>
      </div>
      <div style={bottomAreaStyle}>
        {children} {/* 병아리 이미지를 아래에 둘 수 있음 */}
        <div style={desStyle}>{des}</div>
      </div>
    </div>
  );
}
