# -*- coding: utf-8 -*-
"""
brain.llm_client

이 모듈은 OpenAI Chat/Whisper 등을 호출하기 위한 공통 래퍼를 제공합니다.

- 환경설정: .env에서 OPENAI_API_KEY를 읽어 client 생성
- MODEL: 민원 엔진에서 사용하는 기본 ChatGPT 모델 이름
- TEMP_GLOBAL: 요약/멘트/일반 응답용 기본 temperature
- TEMP_CLASSIFIER: 분류/출동 여부 판단용 temperature
- call_chat(messages, model, temperature, max_tokens): Chat API 래퍼

민원 엔진(minwon_engine)은 이 모듈을 통해서만 LLM을 호출하도록 분리해 두었습니다.
"""

import os
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI


# -------------------- 환경 설정 --------------------
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다.")

client = OpenAI(api_key=API_KEY)

MODEL = "gpt-4o"
TEMP_GLOBAL = 0.2      # 요약/멘트/라우팅 등
TEMP_CLASSIFIER = 0.0  # 분류/출동 여부 판단 (결정적)


# -------------------- OpenAI Chat 호출 래퍼 --------------------
def call_chat(
    messages: List[Dict[str, str]],
    model: str = MODEL,
    temperature: float = TEMP_GLOBAL,
    max_tokens: int = 512,
) -> str:
    """OpenAI Chat 호출 래퍼."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("[WARN] OpenAI API error:", e)
        return ""
