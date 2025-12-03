import type { ReactNode, CSSProperties } from "react";
import Polygon from "../assets/Polygon.png";
import Logo from "../assets/logo2.png";
import GwangjuLogo from "../assets/aischool.png";

interface BubbleLayoutProps {
  title: string;
  topImage?: string;
  content?: string;
  content2?: string;
  content3?: string;
  children?: ReactNode;
  image?: string;
  onClick?: () => void;
}

/** 전체 화면 중앙 정렬 */
const screenWrapperStyle: CSSProperties = {
  width: "100vw",
  height: "100%",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  background: "rgba(142, 209, 71, 0.77)",
};

/** 상단 반투명 바 */
const topBarStyle: CSSProperties = {
  position: "absolute",
  width: "100vw",
  height: "89px",
  top: "0",
  left: "0",
  background: "rgba(250, 250, 250, 0.7)",
  zIndex: 2,
};

/** 제목 탭 */
const titleTabStyle: CSSProperties = {
  position: "absolute",
  width: "500px",
  height: "129px",
  top: "0",
  left: "50%",
  transform: "translateX(-50%)",
  background: "#FFFFFF",
  borderRadius: "0px 0px 60px 60px",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 3,
  borderBlockEnd: "6px solid #668b5a",
};

const titleTextStyle: CSSProperties = {
  fontFamily: "surround",
  fontWeight: 800,
  fontSize: "65px",
  lineHeight: "92px",
  color: "#000000",
};

/** 말풍선 그룹 */
const bubbleGroupStyle: CSSProperties = {
  position: "absolute",
  width: "95vw",
  height: "540px",
  left: "50%",
  top: "50%",
  transform: "translate(-50%, -45%)",
  zIndex: 3,
};

/** 말풍선 몸통 */
const bubbleBodyStyle: CSSProperties = {
  position: "absolute",
  width: "95vw",
  height: "500.3px",
  background: "#FFFFFF",
  borderRadius: "100px",
  top: 0,
  left: 0,
  padding: "40px",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  boxSizing: "border-box",
  zIndex: 2,
  flexDirection: "column",
};

/** 말풍선 꼬리 */
const bubbleTailStyle: CSSProperties = {
  position: "absolute",
  top: "460px",
  right: "330px",
  zIndex: 1,
};

/** 텍스트 스타일 */
const bubbleTextStyle: CSSProperties = {
  fontFamily: "all-bold",
  fontWeight: 400,
  fontSize: "50px",
  textAlign: "center",
  lineHeight: "90px",
  color: "#000000",
};
const smallTextStyle: CSSProperties = {
  position: "absolute",
  bottom: "20px",
  fontFamily: "surround",
  fontWeight: 400,
  fontSize: "30px",
  left: "130px",
};
const smallTextStyle2: CSSProperties = {
  position: "absolute",
  bottom: "-100px",
  fontFamily: "surround",
  fontWeight: 400,
  fontSize: "30px",
};
const imageStyle: CSSProperties = {
  position: "absolute",
  width: "319px",
  height: "319px",
  bottom: "-10px",
  right: "0px",
  zIndex: 4,
  pointerEvents: "none",
};
const logoStyle: CSSProperties = {
  position: "absolute",
  top: "20px",
  right: "20px",
  width: "180px",
  height: "auto",
  zIndex: 4,
};
const GwangjulogoStyle: CSSProperties = {
  position: "absolute",
  bottom: "6px",
  zIndex: 4,
  width: "300px",
  height: "auto",
  left: "20px",
};

const topimageStyle: CSSProperties = {
  position: "absolute",
  top: "19px",
  left: "60px",
  zIndex: 4,
};
// 없앨거
const childrenBelowStyle: CSSProperties = {
  position: "absolute",
  bottom: "30px", // 말풍선보다 아래
  left: "50%",
  transform: "translateX(-50%)",
  width: "100%",
  display: "flex",
  justifyContent: "center",
  zIndex: 3,
  fontFamily: "surround",
};

function renderMultiline(content: string) {
  return content.split("\n").map((line, idx) => <div key={idx}>{line}</div>);
}

export default function BubbleLayout({
  title,
  topImage,
  content,
  content2,
  content3,
  children,
  image,
  onClick,
}: BubbleLayoutProps) {
  return (
    <div style={screenWrapperStyle} onClick={onClick}>
      {/* 상단 타이틀 */}
      <div style={topBarStyle} />
      <img src={Logo} alt="head" style={logoStyle} />
      {topImage && <img src={topImage} alt="top" style={topimageStyle} />}

      <div style={titleTabStyle}>
        <div style={titleTextStyle}>{title}</div>
      </div>

      {/* 말풍선 */}
      <div style={bubbleGroupStyle}>
        <div style={bubbleBodyStyle}>
          {content && (
            <div style={bubbleTextStyle}>{renderMultiline(content)}</div>
          )}
          {content2 && (
            <div style={smallTextStyle}>{renderMultiline(content2)}</div>
          )}
          {content3 && (
            <div style={smallTextStyle2}>{renderMultiline(content3)}</div>
          )}
        </div>
        <img src={Polygon} alt="tail" style={bubbleTailStyle} />
      </div>
      {children && <div style={childrenBelowStyle}>{children}</div>}

      {image && <img src={image} style={imageStyle} />}
      <img src={GwangjuLogo} alt="gwangju" style={GwangjulogoStyle} />
    </div>
  );
}
