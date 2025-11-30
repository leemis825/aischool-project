# brain/classifier.py
# -*- coding: utf-8 -*-
"""
민원 1차 카테고리 분류 모듈.

역할
----
- detect_minwon_type(text):
    규칙 기반으로 민원 상위 카테고리(도로/시설물/연금·복지/심리지원/생활민원/기타)를 결정.
- 쓰러진 나무 + 통행 장애 같은 '안전·위험' 케이스는
  먼저 도로로 강제 분류해서 LLM이 엉뚱하게 분류해도 최소한 도로로 떨어지도록 함.

주의
----
- 여기서는 '상위 카테고리'만 정한다.
  세부 handling_type(단순 안내 / 전화 / 공식 접수)와
  위험도(risk_level)는 minwon_engine 쪽 로직에서 결정한다.
"""

from __future__ import annotations

from typing import Literal

from .utils_text import normalize_korean, contains_any

# 민원 상위 카테고리 타입
MinwonType = Literal["도로", "시설물", "연금/복지", "심리지원", "생활민원", "기타"]

# ------------------------------------------------------------
# 1. 쓰러진 나무(도로 장애) 관련 규칙
# ------------------------------------------------------------

# '나무' 존재 여부
TREE_WORDS = [
    "나무",
    "가로수",
]

# '쓰러지다/넘어지다/부러지다' 계열 동사
TREE_FALL_WORDS = [
    "쓰러지",
    "쓰러져",
    "넘어지",
    "넘어져",
    "부러지",
]

# 통행 장애를 암시하는 표현
BLOCK_WORDS = [
    "통행",
    "지나가",
    "길이 막",
    "길이막",
    "막혀",
    "막혔",
    "대문을 막",
    "대문막",
    "출입문을 막",
    "출입문막",
]


def _is_tree_fall(norm: str) -> bool:
    """정규화된 문자열 기준으로 '나무가 쓰러진 상황'인지 판정."""
    if not any(w in norm for w in TREE_WORDS):
        return False
    return any(w in norm for w in TREE_FALL_WORDS)


def is_tree_block_case(text: str) -> bool:
    """'쓰러진 나무 + 통행 장애' 케이스인지 판정.

    예)
        - 우리 집 앞에 나무가 쓰러져서 통행이 어려워
        - 골목길에 가로수가 쓰러져서 차가 못 지나가

    이 경우:
        - minwon_type 은 '도로'
        - 이후 위험도 로직에서는 기본값을 '긴급'에 가깝게 보도록 사용
    """
    norm = normalize_korean(text)
    if not _is_tree_fall(norm):
        return False
    return any(b in norm for b in BLOCK_WORDS)


# ------------------------------------------------------------
# 2. 일반 카테고리 키워드
# ------------------------------------------------------------

ROAD_KEYWORDS = [
    "도로",
    "길바닥",
    "포장도로",
    "아스팔트",
    "구멍",
    "파였",
    "패인",
]

FACILITY_KEYWORDS = [
    "가로등",
    "신호등",
    "전봇대",
    "전주",
    "놀이터",
    "그네",
    "미끄럼틀",
    "공원",
    "벤치",
]

PENSION_KEYWORDS = [
    "연금",
    "기초연금",
    "국민연금",
    "기초 생활",
    "기초생활",
    "수당",
    "장려금",
]

MENTAL_KEYWORDS = [
    "우울",
    "불안",
    "우울증",
    "공황",
    "상담받고 싶",
    "상담 받고 싶",
    "죽고 싶",
    "죽고싶",
    "자살",
    "힘들어 죽겠",
    "마음이너무",
]

LIFE_KEYWORDS = [
    "쓰레기",
    "불법투기",
    "무단투기",
    "소음",
    "담배연기",
    "담배 냄새",
    "악취",
    "층간소음",
    "주차문제",
    "무단주차",
]


# ------------------------------------------------------------
# 3. 메인 분류 함수
# ------------------------------------------------------------

def detect_minwon_type(text: str) -> MinwonType:
    """입력 텍스트를 보고 1차 민원 카테고리를 결정.

    우선순위
    -------
    1) 쓰러진 나무 + 통행 장애  => '도로'
    2) 쓰러진 나무(통행 언급 없음) => '도로'
    3) 도로 일반 키워드         => '도로'
    4) 시설물 관련 키워드        => '시설물'
    5) 연금/복지 키워드          => '연금/복지'
    6) 심리지원 키워드           => '심리지원'
    7) 생활민원 키워드           => '생활민원'
    8) 그 외                     => '기타'
    """
    norm = normalize_korean(text)

    # 1) 쓰러진 나무 + 통행 장애
    if is_tree_block_case(text):
        return "도로"

    # 2) 쓰러진 나무 (통행 언급 없어도 도로 쪽으로 분류)
    if _is_tree_fall(norm):
        return "도로"

    # 3) 도로 일반 키워드
    if contains_any(norm, ROAD_KEYWORDS):
        return "도로"

    # 4) 시설물
    if contains_any(norm, FACILITY_KEYWORDS):
        return "시설물"

    # 5) 연금/복지
    if contains_any(norm, PENSION_KEYWORDS):
        return "연금/복지"

    # 6) 심리지원
    if contains_any(norm, MENTAL_KEYWORDS):
        return "심리지원"

    # 7) 생활민원
    if contains_any(norm, LIFE_KEYWORDS):
        return "생활민원"

    # 8) 규칙에 안 걸리면 기타
    return "기타"
