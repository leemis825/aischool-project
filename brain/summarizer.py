# brain/summarizer.py
# -*- coding: utf-8 -*-
"""
brain.summarizer

민원 원문을 "짧게 잘 요약"하는 기능을 담당하는 모듈입니다.

주요 기능:
- build_fallback_summary(text, category):
    LLM이 실패했을 때 사용할 단순 요약 문자열 생성.

- summarize_for_user(text, category, handling=None):
    주민에게 들려줄 한 단락/한 줄 요약(Answer Core 또는 안내 문장)을 생성.

- summarize_for_staff(text, category, extra):
    담당 공무원이 빠르게 파악할 수 있는 3줄 요약, 위치, 시간 정보,
    현장 방문 필요 여부, 시민 요청, 키워드, 메모 등을
    JSON 형식으로 반환.
"""

import json
from typing import Any, Dict, List, Optional

from .llm_client import call_chat, MODEL, TEMP_GLOBAL


def build_fallback_summary(text: str, category: str) -> str:
    """
    LLM이 깨지거나 JSON 파싱 실패했을 때 쓰는 아주 단순 요약.
    """
    if not text:
        return f"{category} 관련 민원"
    snippet = text.replace("\n", " ")[:80]
    return f"{category} 관련 민원: {snippet}..."


# ---------------------------------------------------------
# 1) 주민용 요약 (Answer Core / 안내 문장)
# ---------------------------------------------------------

USER_SUMMARY_SYSTEM_PROMPT = (
    "너는 고령층 주민을 위한 민원 상담 도우미야. "
    "다음 민원을 주민에게 들려줄 짧은 안내 문장으로 정리해줘.\n"
    "규칙:\n"
    "1) 존댓말, 너무 딱딱한 공문체 말고 자연스러운 말투.\n"
    "2) 2~3문장 이내로, 핵심만 설명.\n"
    "3) 무엇이 문제인지 + 어떻게 처리될 예정인지 중심으로.\n"
    "4) 위험·안전 관련이면, 담당 부서에서 현장을 확인하고 조치한다는 내용을 포함.\n"
    "5) 애매한 내용은 단정짓지 말고, '담당 부서에서 한 번 더 확인할 예정입니다.' 같은 문장을 덧붙여줘.\n"
)


def summarize_for_user(
    text: str,
    category: str,
    handling: Optional[Dict[str, Any]] = None,
) -> str:
    """
    주민에게 보여줄/들려줄 한 단락 요약.

    - text: 민원 원문
    - category: 엔진이 분류한 민원 유형 (도로, 시설물, 연금/복지 등)
    - handling: handling_type, needs_visit, risk_level 등이 들어 있는 dict (옵션)

    기존 코드와의 호환성을 위해 category는 그대로 받고,
    minwon_engine 쪽에서 넘겨주는 handling 정보를 프롬프트에 참고용으로만 넣는다.
    """
    # handling 정보를 문자열로 정리 (옵션)
    handling_str = ""
    if handling is not None:
        try:
            handling_str = json.dumps(handling, ensure_ascii=False)
        except Exception:
            handling_str = str(handling)

    user_lines: List[str] = [
        f"[카테고리: {category}]",
        "",
        "[민원 원문]",
        text,
    ]
    if handling_str:
        user_lines.extend(
            [
                "",
                "[엔진이 판단한 처리 정보(handling)]",
                handling_str,
            ]
        )

    user_prompt = "\n".join(user_lines)

    try:
        out = call_chat(
            [
                {"role": "system", "content": USER_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL,
            temperature=TEMP_GLOBAL,
            max_tokens=300,
        )
        if out:
            return out.strip()
    except Exception:
        # LLM 호출 자체가 실패하면 아래 fallback 사용
        pass

    # fallback: 아주 단순한 안내 문장
    base = build_fallback_summary(text, category)
    return f"{base} 말씀해 주신 내용은 담당 부서에서 확인 후 처리할 예정입니다."


# ---------------------------------------------------------
# 2) 담당자용 요약 (staff_payload)
# ---------------------------------------------------------

def summarize_for_staff(
    text: str,
    category: str,
    extra: Any | None = None,
) -> Dict[str, Any]:
    """
    담당 공무원용 3줄 요약 + 위치/시간/출동 필요 여부 등.

    minwon_engine.run_pipeline_once 에서 staff_payload 만들 때 사용.

    extra:
      - 엔진이 가진 추가 정보(handling, risk_level 등)를 넘길 수 있는 확장용 필드.
      - 지금은 프롬프트 안에서 참고용으로만 사용.
    """

    # extra를 프롬프트에 같이 넘겨서 LLM이 맥락을 더 잘 보도록 함
    extra_str = ""
    if extra is not None:
        try:
            extra_str = json.dumps(extra, ensure_ascii=False)
        except Exception:
            extra_str = str(extra)

    system = (
        "너는 민원 담당 공무원을 돕는 요약 도우미야. "
        "다음 민원 내용을 보고 JSON으로만 답해. "
        "반드시 다음 필드를 포함해야 해.\n"
        "- summary_3lines: 민원 내용을 2~3줄로 요약한 문장 (텍스트)\n"
        "- location: 민원 발생 위치 (예: '○○동 ○○아파트 앞', 없으면 빈 문자열)\n"
        "- time_info: 민원 발생 시점/기간 (예: '오늘 새벽 3시경', 없으면 빈 문자열)\n"
        "- needs_visit: 현장 방문이 실제로 필요한지 (true/false)\n"
        "- risk_level: '긴급', '보통', '경미' 중 하나\n"
        "- citizen_request: 주민이 실제로 원하는 조치 내용 한 줄\n"
        "- raw_keywords: 주요 키워드 리스트 (예: ['가로등 고장', '횡단보도'])\n"
        "- memo_for_staff: 담당자에게 남길 메모 (선택적, 없으면 짧게라도 작성)\n"
        "- category: 최종 카테고리 문자열 (예: '도로', '시설물', ...)\n\n"
        "JSON 이외의 다른 텍스트(설명, 문장)는 절대 추가하지 마."
    )

    user_parts: List[str] = [
        f"[카테고리: {category}]",
        "다음 민원을 행정 담당자가 보기 쉽게 요약해줘.",
        "",
        "[민원 원문]",
        text,
    ]
    if extra_str:
        user_parts.extend(
            [
                "",
                "[엔진이 판단한 추가 정보(extra)]",
                extra_str,
            ]
        )
    user = "\n".join(user_parts)

    out = call_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=400,
    )

    # 기본 구조
    data: Dict[str, Any] = {
        "summary_3lines": build_fallback_summary(text, category),
        "location": "",
        "time_info": "",
        "needs_visit": False,
        "risk_level": "보통",
        "citizen_request": "",
        "raw_keywords": [],
        "memo_for_staff": "",
        "category": category,
    }

    # LLM 응답 JSON 파싱
    try:
        parsed = json.loads(out)
        if isinstance(parsed, dict):
            data.update(parsed)
    except Exception:
        # 파싱 실패 시, 위에 정의한 기본값을 그대로 사용
        pass

    # 필수 필드 보정
    if not data.get("summary_3lines"):
        data["summary_3lines"] = build_fallback_summary(text, category)

    data.setdefault("location", "")
    data.setdefault("time_info", "")
    data.setdefault("needs_visit", False)
    data.setdefault("risk_level", "보통")
    data.setdefault("citizen_request", "")
    data.setdefault("raw_keywords", [])
    data.setdefault("memo_for_staff", "")
    data.setdefault("category", category)

    # 타입 안전장치
    if not isinstance(data["raw_keywords"], list):
        data["raw_keywords"] = [str(data["raw_keywords"])]

    return data
