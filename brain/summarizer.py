# brain/summarizer.py
# -*- coding: utf-8 -*-
"""
brain.summarizer

민원 원문을 "짧게 잘 요약"하는 기능을 담당하는 모듈입니다.

주요 기능:
- build_fallback_summary(text, category):
    LLM이 실패했을 때 사용할 단순 요약 문자열 생성.
- summarize_for_user(text, category):
    주민에게 들려줄 한 줄 요약(Answer Core)을 생성.
- summarize_for_staff(text, category):
    담당 공무원이 빠르게 파악할 수 있는 3줄 요약, 위치, 시간 정보,
    현장 방문 필요 여부 등을 JSON 형식으로 반환.
"""

import json
from typing import Any, Dict

from .llm_client import call_chat, MODEL, TEMP_GLOBAL


def build_fallback_summary(text: str, category: str) -> str:
    """
    LLM이 깨지거나 JSON 파싱 실패했을 때 쓰는 아주 단순 요약.
    """
    return f"{category} 관련 민원: {text[:80]}..." if text else ""


def summarize_for_user(text: str, category: str) -> str:
    """
    주민에게 보여줄/들려줄 한 줄 요약(질문 요약).

    예)
      - "1938년생이신데, 연금 수령 시작 시기가 궁금하시군요!"
      - "집 앞에 쓰러진 나무 때문에 통행이 어려운 상황을 말씀해 주셨습니다."
    """
    system = (
        "너는 민원 상담 도우미야. "
        "다음 민원을 '주민에게 들려줄 한 문장'으로 공손하게 요약해줘. "
        "너무 딱딱한 공문 스타일이 아니라, 사람 말투로 정리해줘."
    )
    user = f"[카테고리: {category}]\n다음 민원을 한 문장으로 요약해줘.\n\n{text}"

    out = call_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=200,
    )

    return out or build_fallback_summary(text, category)


def summarize_for_staff(text: str, category: str) -> Dict[str, Any]:
    """
    담당 공무원용 3줄 요약 + 위치/시간/출동 필요 여부.
    minwon_engine.run_pipeline_once 에서 staff_payload 만들 때 사용.
    """
    system = (
        "너는 민원 담당 공무원을 돕는 요약 도우미야. "
        "다음 민원 내용을 보고 JSON으로만 답해. "
        "반드시 summary_3lines, location, time_info, needs_visit, risk_level 필드를 포함해야 해."
    )
    user = f"[카테고리: {category}]\n다음 민원을 요약해줘.\n\n{text}"

    out = call_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=300,
    )

    try:
        data = json.loads(out)
    except Exception:
        # LLM이 JSON 형식으로 못 줬을 때의 안전장치
        data = {
            "summary_3lines": build_fallback_summary(text, category),
            "location": "",
            "time_info": "",
            "needs_visit": False,
            "risk_level": "보통",
        }

    # 누락 필드 기본값 채우기
    data.setdefault("summary_3lines", build_fallback_summary(text, category))
    data.setdefault("location", "")
    data.setdefault("time_info", "")
    data.setdefault("needs_visit", False)
    data.setdefault("risk_level", "보통")

    return data
