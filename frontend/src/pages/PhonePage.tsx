import { useNavigate } from "react-router-dom";
import { useState } from "react";
import Layout from "../components/Layout.js";
import BackIcon from "../assets/back.png";

export default function PhonePage() {
  const navigate = useNavigate();
  const [digits, setDigits] = useState("");

  const handleNumberClick = (n: string) => {
    setDigits((prev) => {
      if (prev.length >= 11) return prev; // 01012341234 까지
      return prev + n;
    });
  };

  const handleBackspace = () => {
    setDigits((prev) => prev.slice(0, -1));
  };

  const formatPhone = (value: string) => {
    if (value.length <= 3) return value;
    if (value.length <= 7) return `${value.slice(0, 3)}-${value.slice(3)}`;
    return `${value.slice(0, 3)}-${value.slice(3, 7)}-${value.slice(7, 11)}`;
  };

  const handleConfirm = () => {
    // 번호 입력 끝나고 다음 페이지로 이동 등
    navigate("/success");
  };

  const numbers = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "←"];

  return (
    <Layout title="번호등록" topImage="src/assets/top2.png">
      {/* 왼쪽: 숫자 키패드 */}
      <div
        style={{
          marginLeft: "60px",
          marginRight: "100px",
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gridTemplateRows: "repeat(4, 1fr)",
          rowGap: "20px",
          columnGap: "30px",
          alignItems: "center",
          justifyItems: "center",
        }}
      >
        {numbers.map((label, idx) => {
          if (label === "") {
            // 빈 칸 (10자리 레이아웃 맞추기 위함)
            return <div key={idx} />;
          }

          // 삭제 버튼
          if (label === "←") {
            return (
              <div
                key={idx}
                onClick={handleBackspace}
                style={{
                  width: "144px",
                  height: "99px",
                  borderRadius: "40px",
                  border: "2px solid #A1D56B",
                  background: "#FFFFFF",
                  boxShadow: "0px 4px 4px rgba(0,0,0,0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
              >
                <img
                  src={BackIcon}
                  alt="back"
                  style={{
                    width: "80px",
                    height: "50px",
                    pointerEvents: "none",
                  }}
                />
              </div>
            );
          }
          // 일반 숫자 버튼 (초록 테두리 원형)
          return (
            <button
              key={idx}
              onClick={() => handleNumberClick(label)}
              style={{
                width: "140px",
                height: "100px",
                borderRadius: "20px",
                border: "3px solid #A1D56B",
                background: "#FFFFFF",
                boxShadow: "0px 4px 4px rgba(0,0,0,0.25)",
                fontFamily: "KoddiUD OnGothic",
                fontWeight: 800,
                fontSize: "45px",
                lineHeight: "85px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* 오른쪽: 안내 문구 + 번호 표시 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          paddingRight: "40px",
        }}
      >
        <div
          style={{
            fontFamily: "KoddiUD OnGothic",
            fontWeight: 400,
            fontSize: "50px",
            lineHeight: "70px",
            textAlign: "left",
            marginBottom: "60px",
            textAlignLast: "center",
          }}
        >
          연락 받으실
          <br />
          번호를 입력해주세요
        </div>

        <div
          style={{
            fontFamily: "KoddiUD OnGothic",
            fontWeight: 400,
            fontSize: "50px",
            lineHeight: "61px",
            textAlign: "left",
            marginBottom: "10px",
            height: "70px",
          }}
        >
          {digits ? formatPhone(digits) : ""}
        </div>

        <div
          style={{
            width: "471px",
            borderBottom: "3px solid #A1D56B",
            marginBottom: "40px",
          }}
        />

        <button
          onClick={handleConfirm}
          style={{
            marginTop: "10px",
            padding: "16px 32px",
            borderRadius: "20px",
            border: "none",
            background: "#A1D56B",
            color: "#FFFFFF",
            fontSize: "32px",
            fontFamily: "KoddiUD OnGothic",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          확인
        </button>
      </div>
    </Layout>
  );
}
