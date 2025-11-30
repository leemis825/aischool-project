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
