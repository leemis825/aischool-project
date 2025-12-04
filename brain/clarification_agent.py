# -*- coding: utf-8 -*-
"""
brain.clarification_agent

추가 질문(clarification)이 필요한지 여부만 판단하는
작은 LLM 에이전트 모듈입니다.

입력:
- text         : 현재까지 모인 민원 텍스트(effective_text)
- minwon_type  : 민원 분류 결과(도로, 시설물, 연금/복지, 심리지원, 생활민원, 기타)
- staff_payload: summarize_for_staff() 결과(JSON 딕셔너리)
- handling_info: handling 결정 정보(handling_type, needs_visit, risk_level 등)

출력 예:
{
  "needs_clarification": true,
  "target": "location",  # "location" | "time" | "both" | "none"
  "reason": "위치가 우리 동네/집 앞 수준으로만 언급되어 있어 모호함"
}
"""

from typing import Any, Dict
import json

from .llm_client import call_chat, MODEL, TEMP_CLASSIFIER


def decide_clarification_with_llm(
    text: str,
    minwon_type: str,
    staff_payload: Dict[str, Any],
    handling_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    LLM에게 '추가 질문이 필요한지'만 묻는 작은 에이전트.

    반환 형식:
    {
      "needs_clarification": bool,
      "target": "location" | "time" | "both" | "none",
      "reason": str,
    }
    """

    system_prompt = """
너는 민원 접수 도우미야.
아래 정보를 보고 '추가 질문이 필요한지'를 판단해.

- 출동(현장 방문)이 필요하면, 위치나 시간 정보가 모호하면 재질문을 권장해.
- 출동이 필요 없고 단순 안내로 충분하면, 웬만하면 재질문을 하지 마.
- 질문은 최소화해서, 주민이 너무 자주 다시 말하지 않도록 하는 것이 목표야.

JSON 하나로만 답해.
형식:
{"needs_clarification": true/false,
 "target": "location" 또는 "time" 또는 "both" 또는 "none",
 "reason": "한국어로 1줄 설명"}

다른 말은 절대 하지 마. 설명 문장이나 주석 없이 JSON만 반환해.
""".strip()

    user_payload = {
        "category": minwon_type,
        "text": text,
        "staff_payload": staff_payload,
        "handling_info": handling_info,
        "instruction": """
판단 기준:

1) 도로/시설물 민원 + 출동 필요(현장 점검/수리)인데
   위치가 '우리 집 앞', '우리 동네', '근처', '큰 파란 대문집'처럼 모호하면
   -> needs_clarification = true, target = "location".

2) 가로등, 신호등, 전선, 쓰러진 나무, 도로 파손 등
   안전/시설 관련 민원은 출동 필요 가능성이 높다.
   위치가 전혀 없거나 너무 모호하면 재질문을 추천해.

3) 연금/복지/심리지원처럼 상담 위주 민원은,
   위치/시간이 모호하더라도 보통 재질문하지 않는다.
   대신 전화 상담 연결을 권장하는 쪽으로 두어라.

4) 이미 위치와 시간이 충분히 구체적이면 재질문하지 말고,
   needs_clarification = false 로 설정해.

5) 재질문이 필요 없다고 판단되면
   target은 항상 "none" 으로 두어라.
""".strip(),
    }

    user_content = json.dumps(user_payload, ensure_ascii=False, indent=2)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # LLM 호출
    resp = call_chat(
        model=MODEL,
        messages=messages,
        temperature=TEMP_CLASSIFIER,
    )

    # 응답 JSON 파싱 (실패 시 안전한 기본값)
    needs_clarification = False
    target = "none"
    reason = ""

    try:
        data = json.loads(resp)
        needs_clarification = bool(data.get("needs_clarification", False))
        target = data.get("target") or "none"
        reason = data.get("reason") or ""
    except Exception:
        # 파싱 실패 시에는 재질문 없이 진행
        needs_clarification = False
        target = "none"
        reason = ""

    return {
        "needs_clarification": needs_clarification,
        "target": target,
        "reason": reason,
    }
