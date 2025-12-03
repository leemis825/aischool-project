# -*- coding: utf-8 -*-
"""
brain.turn_router

하나의 세션 안에서 여러 개의 민원이 섞여 나올 수 있을 때,
각 턴을 'A', 'B', 'C' 같은 이슈 단위로 묶어 주는 역할을 합니다.

예시:
- A: '우리 집 앞 나무가 쓰러졌어' 관련 대화 묶음
- B: '도로에 구멍 난 거' 관련 대화 묶음
- 다시 A로 돌아와서 '그 나무는 언제 치워져?' 같은 질문이 나올 수 있음

주요 기능(예시):
- choose_issue_for_followup(...):
    새로 들어온 발화를 기존 이슈 중 어디에 붙일지,
    아니면 새 이슈로 만들지 결정하는 로직.
- (필요 시) similarity / 규칙 기반 매칭.

이 모듈의 결과인 issue_id(A/B/C)는
로그 분석·어드민 통계에서 "민원 단위"로 활용할 수 있습니다.
"""


from __future__ import annotations

import json
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다.")

client = OpenAI(api_key=API_KEY)

# 멀티턴 라우팅은 약간의 추론이 필요하므로 gpt-4o를 사용
MODEL = os.getenv("OPENAI_MODEL_ROUTER", "gpt-4o")
TEMP_ROUTER = 0.2


def _build_issues_description(issues: Dict[str, dict]) -> str:
    """
    이슈 목록을 LLM에 주기 좋은 텍스트로 변환합니다.

    issues: {
      "A": {"category": "...", "brief": "...", "status": "open/closed"},
      "B": {...},
    }
    """
    lines = []
    for issue_id, info in issues.items():
        cat = info.get("category") or "미분류"
        brief = info.get("brief", "")
        status = info.get("status", "open")
        lines.append(f"- 이슈 {issue_id} (상태: {status}, 카테고리: {cat})\n  요약: {brief}")
    return "\n".join(lines)


def choose_issue_for_followup(
    current_text: str,
    issues_for_router: Dict[str, dict],
) -> Optional[str]:
    """
    현재 발화가 기존 이슈들 중 하나의 '후속 발화'인지,
    아니면 완전히 새로운 민원인지 판별합니다.

    issues_for_router 예시:
    {
      "A": {"category": "도로", "brief": "우리집 앞에 나무가 쓰러져서 통행이 어려워", "status": "closed"},
      "B": {"category": "생활민원", "brief": "동곡리 마을회관 앞에 쓰레기 폐기물이 있어서 불편", "status": "open"},
      ...
    }

    반환:
      - "A", "B" 등 issues_for_router에 존재하는 key → 해당 이슈의 후속
      - None → 새로운 민원으로 처리
    """
    if not issues_for_router:
        return None

    issues_description = _build_issues_description(issues_for_router)

    system_prompt = (
        "너는 마을 민원 시스템의 대화 라우팅 보조 도우미야. "
        "사용자의 현재 발화가, 과거에 존재하는 어느 민원 이슈의 '연속/후속/관련 질문'인지 "
        "아니면 완전히 새로운 민원인지 판단해야 해.\n\n"
        "반드시 JSON만 출력해야 해.\n"
        "형식: {\"target_issue\": \"A\" 또는 \"B\" 또는 \"none\", \"reason\": \"설명\"}\n"
        "target_issue는 아래 중 하나여야 해:\n"
        "- 기존 이슈 ID (예: \"A\", \"B\" ...)\n"
        "- \"none\" (어느 이슈와도 충분히 관련 없거나 모호한 경우)\n\n"
        "주의:\n"
        "- 과도하게 억지로 연결하지 말고, 모호하면 \"none\"을 선택해.\n"
        "- 대명사(그거, 그 나무, 아까 그거 등)로 이전 내용을 가리키는 경우, "
        "맥락상 가장 자연스러운 이슈를 고르면 돼.\n"
    )

    user_prompt = (
        f"현재 사용자 발화:\n"
        f"\"{current_text}\"\n\n"
        f"기존 이슈 목록:\n"
        f"{issues_description}\n\n"
        f"질문: 현재 발화는 위 이슈들 중 어느 것의 후속 발화로 보는 것이 가장 자연스러운가?\n"
        f"해당 이슈의 ID(예: \"A\" 또는 \"B\") 또는 \"none\"을 JSON 형식으로만 답하라."
    )

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMP_ROUTER,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    try:
        content = resp.choices[0].message.content
        data = json.loads(content)
        target = data.get("target_issue", "none")
        if target == "none":
            return None
        if target in issues_for_router:
            return target
        # 이상한 값이면 None 처리
        return None
    except Exception:
        # 파싱 실패 등 → 보수적으로 새 이슈로 처리
        return None
