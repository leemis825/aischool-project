import type { ReactNode, CSSProperties } from "react";

interface LayoutProps {
  title: string;
  content: string;
  headerImage?: string;
  children?: ReactNode;
  onClick?: () => void;
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
  flexDirection: "column",
};

/* 상단 작은 흰 영역 */
const topWhiteStyle: CSSProperties = {
  position: "absolute",
  width: "375px",
  height: "129px",
  background: "#FFFFFF",
  top: "0",

  borderRadius: "0px 0px 60px 60px",
};

// 이미지
const headerImageStyle: CSSProperties = {
  position: "absolute",
  top: "5px",
  right: "150px",
  width: "230px",
  height: "auto",
  pointerEvents: "none",
  zIndex: 10,
};
/* 상단 제목 */
const titleStyle: CSSProperties = {
  position: "absolute",
  top: "10px",
  width: "100%",
  textAlign: "center",
  fontFamily: "KoddiUD OnGothic",
  fontWeight: 800,
  fontSize: "75px",
  color: "#000000",
};

const whiteCardStyle: CSSProperties = {
  position: "absolute",
  bottom: 0,
  width: "100vw",
  height: "500px",
  background: "#FFFFFF",
  borderRadius: "150px 150px 0 0",

  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  paddingTop: "160px", // content와 topWhite 사이 공간
};

/* 본문 내용 */
const contentStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "auto",
  textAlign: "center",
  fontFamily: "KoddiUD OnGothic",
  fontWeight: 700,
  fontSize: "100px",
  color: "#000000",
  top: "-100px",
};

const childrenWrapperStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  display: "flex",
  justifyContent: "center",
  marginTop: "-20px",
};
function renderMultiline(content: string) {
  return content.split("\n").map((line, idx) => <div key={idx}>{line}</div>);
}

export default function Layout({
  title,
  content,
  headerImage,
  children,
  onClick,
}: LayoutProps) {
  return (
    <div style={wrapperStyle} onClick={onClick}>
      <div style={topWhiteStyle}></div>
      {headerImage && (
        <img
          src={headerImage}
          alt="header decoration"
          style={headerImageStyle}
        />
      )}
      <div style={titleStyle}>{title}</div>
      <div style={whiteCardStyle}>
        <div style={contentStyle}>{renderMultiline(content)}</div>
        <div style={childrenWrapperStyle}>{children}</div>
      </div>
    </div>
  );
}
