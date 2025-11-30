# core/config.py
# -*- coding: utf-8 -*-

import os
from pathlib import Path

# 프로젝트 루트 기준
BASE_DIR = Path(__file__).resolve().parent.parent

# 로그 디렉토리 (지금과 동일)
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------
# 외부 API 키 / URL 설정
# -------------------------------

# WeatherAPI.com
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = "http://api.weatherapi.com/v1/current.json"

# 한국천문연구원(OpenAPI)
KASI_SERVICE_KEY = os.getenv("KASI_SERVICE_KEY")
KASI_LUNAR_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo"
)
KASI_24DIV_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/get24DivisionsInfo"
)

# 네이버 TTS
NAVER_API_KEY_ID = os.getenv("NAVER_API_KEY_ID")
NAVER_API_KEY = os.getenv("NAVER_API_KEY")
NAVER_TTS_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

# OpenAI (STT/번역)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Whisper / 번역용 모델 (없으면 기본값)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "gpt-4o-mini-transcribe")
CHAT_MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")
