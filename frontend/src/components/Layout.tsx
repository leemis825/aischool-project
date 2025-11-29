import type { ReactNode, CSSProperties } from "react";
import Logo from "../assets/logo2.png";
import GwangjuLogo from "../assets/aischool.png";

interface LayoutProps {
  title: string;
  topImage?: string;
  content?: string;
  footerImage?: string;
  children?: ReactNode;
  image?: string;
  onClick?: () => void;
}
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

const logoStyle: CSSProperties = {
  position: "absolute",
  top: "20px",
  right: "20px",
  width: "180px",
  height: "auto",
  zIndex: 4,
};

/* 상단 제목 */
const titleStyle: CSSProperties = {
  position: "absolute",
  top: "10px",
  width: "100%",
  textAlign: "center",
  fontFamily: "surround",
  fontWeight: 800,
  fontSize: "75px",
  color: "#000000",
};

const whiteCardStyle: CSSProperties = {
  position: "absolute",
  width: "95vw",
  height: "410px",
  background: "#FFFFFF",
  borderRadius: "100px",
  top: "160px",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  paddingTop: "160px", // content와 topWhite 사이 공간
  overflow: "hidden",
  borderBlockEnd: "8px solid #668b5a",
};
const topimageStyle: CSSProperties = {
  position: "absolute",
  top: "19px",
  left: "60px",
  zIndex: 4,
};

const imageStyle: CSSProperties = {
  position: "absolute",
  width: "319px",
  height: "319px",
  bottom: "0px",
  right: "10px",
  zIndex: 4,
  pointerEvents: "none",
};

/* 본문 내용 */
const contentStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "auto",
  textAlign: "center",
  fontFamily: "all-bold",
  fontWeight: 500,
  fontSize: "80px",
  color: "#000000",
  top: "-120px",
  lineHeight: "120px",
  marginBottom: "40px",
  marginTop: "20px",
};

const childrenWrapperStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  display: "flex",
  justifyContent: "center",
  marginTop: "-110px",
  fontFamily: "surround",
};

const footerImageStyle: CSSProperties = {
  position: "absolute",
  bottom: "-23px",
  right: "40px",
  pointerEvents: "none",
};

const GwangjulogoStyle: CSSProperties = {
  position: "absolute",
  bottom: "6px",
  zIndex: 4,
  width: "300px",
  height: "auto",
  left: "20px",
};

function renderMultiline(content: string) {
  return content.split("\n").map((line, idx) => <div key={idx}>{line}</div>);
}

export default function Layout({
  title,
  content,
  topImage,
  footerImage,
  children,
  image,
  onClick,
}: LayoutProps) {
  return (
    <div style={screenWrapperStyle} onClick={onClick}>
      <div style={topBarStyle}></div>
      <img src={Logo} alt="head" style={logoStyle} />
      {topImage && <img src={topImage} alt="top" style={topimageStyle} />}

      <div style={titleTabStyle}>
        <div style={titleTextStyle}>{title}</div>
      </div>

      <div style={titleStyle}>{title}</div>
      <div style={whiteCardStyle}>
        {content && <div style={contentStyle}>{renderMultiline(content)}</div>}
        <div style={childrenWrapperStyle}>{children}</div>
        {footerImage && (
          <img
            src={footerImage}
            alt="footer decoration"
            style={footerImageStyle}
          />
        )}
      </div>
      {image && <img src={image} style={imageStyle} />}
      <img src={GwangjuLogo} alt="gwangju" style={GwangjulogoStyle} />
    </div>
  );
}
