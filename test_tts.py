# test_tts.py
from dotenv import load_dotenv
import os
import requests

# .env 불러오기
load_dotenv()

NAVER_API_KEY_ID = os.getenv("NAVER_API_KEY_ID")
NAVER_API_KEY = os.getenv("NAVER_API_KEY")

print("KEY_ID:", NAVER_API_KEY_ID)
print("KEY:", NAVER_API_KEY)
# 네이버 TTS 기본 URL — 콘솔 문서 기준
NAVER_TTS_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

def test_tts():
    if not NAVER_API_KEY_ID or not NAVER_API_KEY:
        print("❌ .env에 NAVER_API_KEY_ID 또는 NAVER_API_KEY가 없습니다.")
        return

    text = "안녕하세요. 간편 민원 안내기 음성 테스트입니다."

    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_API_KEY_ID,
        "X-NCP-APIGW-API-KEY": NAVER_API_KEY,
    }

    data = {
        "speaker": "nara",   # 네이버 TTS 기본 여화자 예시
        "speed": "0",
        "text": text,
    }

    print("📡 네이버 TTS 호출 중...")

    res = requests.post(NAVER_TTS_URL, headers=headers, data=data)
    try:
        res.raise_for_status()
    except Exception as e:
        print("❌ TTS 호출 실패:", e)
        print("응답:", res.text)
        return

    with open("tts_test.mp3", "wb") as f:
        f.write(res.content)

    print("✅ 완료: tts_test.mp3 파일이 생성되었습니다.")
    print("👉 파일 더블클릭해서 음성 확인하세요!")


if __name__ == "__main__":
    test_tts()
