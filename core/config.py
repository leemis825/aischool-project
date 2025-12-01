# core/config.py
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from dotenv import load_dotenv

# .env 로드 (가장 먼저 실행)
load_dotenv()

# --------------------------------
# 경로 / 로그 디렉터리 설정
# --------------------------------

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

# 로그 디렉터리
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------
# 외부 API 키 / URL 설정
# --------------------------------

# 1) WeatherAPI.com
#    - 현재는 current.json(현재 날씨) 엔드포인트를 사용
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = "http://api.weatherapi.com/v1/forecast.json"

# 2) 한국천문연구원(OpenAPI)
#    - 공통 서비스키(.env에 KASI_SERVICE_KEY 로 저장)
KASI_SERVICE_KEY = os.getenv("KASI_SERVICE_KEY")

#    - 음력 변환
KASI_LUNAR_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/"
    "LrsrCldInfoService/getLunCalInfo"
)

#    - 24절기 정보
KASI_24DIV_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/"
    "SpcdeInfoService/get24DivisionsInfo"
)

#    - 공휴일 정보 (필요할 때 사용)
KASI_HOLIDAY_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/"
    "SpcdeInfoService/getHoliDeInfo"
)
KASI_BASE_URL = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
# 3) 네이버 CLOVA TTS
NAVER_API_KEY_ID = os.getenv("NAVER_API_KEY_ID")
NAVER_API_KEY = os.getenv("NAVER_API_KEY")
NAVER_TTS_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

# 4) OpenAI (STT / 번역 / LLM)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Whisper / 번역용 모델 (환경변수 없으면 기본값 사용)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "gpt-4o-mini-transcribe")
CHAT_MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")
