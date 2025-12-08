# -*- coding: utf-8 -*-
"""
brain.utils_text

민원 텍스트 공통 유틸 모듈.

역할
----
- normalize_korean(text): 한글 중심 정규화 (소문자/공백/특수문자 정리)
- normalize(text): 일반 정규화 (지금은 normalize_korean을 thin wrapper 로 사용)
- contains_any(text, keywords): 키워드 리스트 중 하나라도 포함되는지 체크
- is_critical(text): '위험·안전 관련 긴급 민원' 여부 판정
- extract_keywords(text): 간단 키워드 리스트 추출
- split_additional_location(text): "추가 위치 정보:" 패턴을 기준으로 본문/추가 위치 분리

이 모듈은 다른 brain 모듈들에서만 공통으로 사용한다.
"""

from __future__ import annotations

import re
from typing import List, Tuple


# ------------------------------------------------------------
# 1. 기본 정규화 함수들
# ------------------------------------------------------------

def normalize_korean(text: str) -> str:
    """
    한글 위주의 민원 텍스트를 비교/검색하기 쉽도록
    - 양 끝 공백 제거
    - 소문자 변환
    - 줄바꿈을 공백으로
    - 연속 공백을 하나로
    정도만 가볍게 정리한다.
    """
    if not text:
        return ""

    t = text.strip().lower()
    t = t.replace("\n", " ")
    # 불필요한 특수문자 제거 (한글/숫자/영어/공백만 남김)
    t = re.sub(r"[^0-9a-z가-힣\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def normalize(text: str) -> str:
    """
    minwon_engine 쪽에서 사용하는 일반 normalize.

    현재 프로젝트에서는 한글 위주이므로 normalize_korean 과 동일하게 동작시킨다.
    나중에 다국어 처리 등이 필요하면 여기만 확장하면 된다.
    """
    return normalize_korean(text)


def contains_any(text: str, keywords: List[str]) -> bool:
    """
    text 안에 keywords 중 하나라도 포함되어 있으면 True.
    이미 normalize_korean을 거쳤다는 가정하에 단순 포함 체크만 한다.
    """
    if not text:
        return False

    return any(kw in text for kw in keywords)


# ------------------------------------------------------------
# 2. 위험도 관련 유틸
# ------------------------------------------------------------

_CRITICAL_KEYWORDS = [
    "쓰러지", "쓰러진나무", "넘어진나무", "나무가넘어져",
    "불났", "불이났", "화재",
    "폭발", "가스냄새",
    "전선", "감전",
    "피가", "피를",
    "폭행", "위협", "칼부림",
    "자살", "죽고 싶", "극단적",
]


def is_critical(text: str) -> bool:
    """
    안전/생명과 직접 관련될 수 있는 긴급 민원인지 여부를 단순 규칙으로 판별.

    - 나무 쓰러짐 + 통행 장애
    - 화재/폭발/가스/전선/감전
    - 피/폭행/위협
    - 자살·죽고 싶다 등 표현

    등이 들어가면 True 를 반환한다.
    """
    if not text:
        return False

    norm = normalize_korean(text)
    return any(kw in norm for kw in _CRITICAL_KEYWORDS)


# ------------------------------------------------------------
# 3. 키워드 추출 유틸
# ------------------------------------------------------------

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    아주 단순한 방식으로 키워드 리스트를 만들어낸다.
    - normalize 후 공백 기준으로 split
    - 길이 1 글자인 토큰은 버림
    - 중복 제거
    """
    norm = normalize_korean(text)
    if not norm:
        return []

    tokens = norm.split()
    seen = set()
    keywords: List[str] = []

    for tok in tokens:
        if len(tok) <= 1:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        keywords.append(tok)
        if len(keywords) >= max_keywords:
            break

    return keywords


# ------------------------------------------------------------
# 4. "추가 위치 정보" 패턴 분리
# ------------------------------------------------------------

_ADDITIONAL_LOC_MARKERS = [
    "추가 위치 정보:",
    "추가위치정보:",
    "추가 위치정보:",
    "추가위치 정보:",
]


def split_additional_location(text: str) -> Tuple[str, str]:
    """
    minwon_engine에서 clarify 후 문장을 합칠 때

        prev_text + " 추가 위치 정보: " + answer

    같은 형태로 붙이기 때문에,
    여기서는 위 패턴을 기준으로 앞부분(원래 민원)과 뒷부분(추가 위치)을 나눈다.

    return: (main_text, extra_location)
    """
    if not text:
        return "", ""

    for marker in _ADDITIONAL_LOC_MARKERS:
        if marker in text:
            main, extra = text.split(marker, 1)
            return main.strip(), extra.strip()

    # 마커가 없으면 전체를 본문으로 간주
    return text.strip(), ""

