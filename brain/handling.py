# -*- coding: utf-8 -*-
"""
brain.handling

민원을 어떻게 처리할지(단순 안내 / 전화 연결 / 공식 민원 접수)를
결정하는 로직과 "추가 질문(clarification)이 필요한 상황"을 관리하는 모듈입니다.

주요 기능:
- decide_handling_from_struct(category, needs_visit, risk_level, text):
    simple_guide / contact_only / official_ticket 중 어떤 처리 방식이 맞는지,
    전화 연결/공식 접수 필요 여부 플래그를 결정.

- need_clarification(summary_data, category, text):
    위치/시간 정보가 부족한데 출동이 필요해 보이는 경우
    한 번 더 위치를 물어볼지 여부 판단.

- build_clarification_response(...):
    추가 위치 정보를 요청하는 user_facing / staff_payload 구조를 만들어
    stage="clarification" 결과로 반환.

민원 엔진의 "처리 전략"에 해당하는 계층입니다.
"""
# brain/handling.py

from typing import Literal
from .utils_text import normalize_korean
from .classifier import MinwonType, is_tree_block_case
from typing import Dict, Any 

RiskLevel = Literal["긴급", "보통", "경미"]

def detect_risk_level(text: str, minwon_type: MinwonType) -> RiskLevel:
    norm = normalize_korean(text)

    # 쓰러진 나무 + 통행 장애는 긴급 처리
    if is_tree_block_case(norm):
        return "긴급"

    # 심리지원 쪽은 위험도 높게
    if minwon_type == "심리지원":
        return "긴급"

    # 기타 시설/생활은 기본 보통
    return "보통"


def decide_handling(minwon_type: MinwonType, text: str) -> dict:
    """
    minwon_type + 텍스트를 기반으로
    - handling_type
    - need_call_transfer
    - need_official_ticket
    - risk_level
    - needs_visit
    를 정리해서 dict로 반환.
    """
    risk_level = detect_risk_level(text, minwon_type)
    needs_visit = False
    handling_type = "simple_guide"
    need_call_transfer = False
    need_official_ticket = False

    # 쓰러진 나무 + 통행 장애 → 현장 방문 + 공식 민원
    norm = normalize_korean(text)
    if is_tree_block_case(norm):
        handling_type = "official_ticket"
        need_official_ticket = True
        needs_visit = True

    elif minwon_type == "도로":
        # 도로지만 위험도가 낮으면 공식민원 or 단순안내 중간선
        handling_type = "official_ticket"
        need_official_ticket = True
        needs_visit = True

    elif minwon_type in ("연금/복지", "심리지원"):
        handling_type = "simple_guide"
        need_call_transfer = True  # 전화 상담 권장

    # 나머지는 기본 단순 안내
    return {
        "handling_type": handling_type,
        "need_call_transfer": need_call_transfer,
        "need_official_ticket": need_official_ticket,
        "risk_level": risk_level,
        "needs_visit": needs_visit,
    }

def need_clarification(
    summary_data: Dict[str, Any],
    minwon_type: MinwonType,
    text: str,
) -> bool:
    """
    요약 결과 + 카테고리를 보고 '추가 질문(clarification) 1턴 더 받아야 하는지' 판단.

    - 도로/시설물처럼 '현장 출동'이 필요한 민원인데
    - 위치 정보가 비어 있거나 너무 모호하면
      => 한 번 더 위치를 물어보도록 True 반환.
    """
    # summarizer 가 내려준 값들
    location = (summary_data.get("location") or "").strip()
    needs_visit = bool(summary_data.get("needs_visit"))
    risk_level = summary_data.get("risk_level", "보통")

    # 출동 필요 없는 민원은 굳이 추가 질문 안 함
    if not needs_visit:
        return False

    # 도로/시설물 위주로만 강하게 적용
    if minwon_type not in ("도로", "시설물"):
        return False

    # 위치가 비어 있거나, summarizer 가 쓰는 placeholder인 경우
    if not location or location in ("명시되지 않음", "미상", "알 수 없음"):
        return True

    # 그 외에는 일단 통과
    return False

def build_clarification_response(
    minwon_type: MinwonType,
    text: str,
) -> Dict[str, Any]:
    """
    위치/시간 정보가 부족해서 추가 질문이 필요한 경우,
    주민용/담당자용 구조를 만들어 돌려준다.
    """
    # 공무원 입장 요약은 간단히만 정리 (필요하면 나중에 LLM 요약으로 교체 가능)
    fallback_summary = f"{minwon_type} 관련 민원: {text[:30]}..."

    user_facing = {
        "short_title": "추가 위치 확인",
        "main_message": "말씀해 주신 내용 잘 들었습니다. 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "next_action_guide": "예를 들면 '○○동 ○○아파트 앞', '○○리 마을회관 앞 골목'처럼 말씀해 주세요.",
        "phone_suggestion": "",
        "confirm_question": "",  # clarification 단계에서는 '이대로 접수할까요?' 질문 안 함
        # 선택: TTS용 스크립트 별도로 쓰고 싶으면 여기 필드 추가
    }

    staff_payload = {
        "summary": fallback_summary,
        "category": f"{minwon_type}-추가 위치 확인 필요",
        "location": "",                # 아직 모름
        "time_info": "",               # 시간도 없으면 빈 값
        "risk_level": "보통",
        "needs_visit": True,           # 여기까지 왔다는 건 출동 필요라 가정
        "citizen_request": text,
        "raw_keywords": [],
        "memo_for_staff": "위치 정보 부족으로 추가 질문 단계. 다음 턴에서 위치를 받을 예정입니다.",
    }

    return {
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }
