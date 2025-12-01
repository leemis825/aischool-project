# -*- coding: utf-8 -*-
"""
rules_pension.py

연금/복지(특히 국민연금) 관련 질의를 처리하기 위한 유틸 모듈.

- compute_pension_age(birth_year): 출생연도 → 연금 수령 시작 나이(만 나이)
- build_pension_message(text): 사용자가 말한 문장에서 출생연도를 뽑아
  "몇 세부터 받을 수 있다"는 한 줄 안내 문장을 만들어 준다.
"""

import re
from typing import Optional


def extract_birth_year(text: str) -> Optional[int]:
    """
    "1938년생", "1990 년 생", "1999년" 같은 패턴에서 출생연도(년)만 추출.
    못 찾으면 None 반환.
    """
    # 1) "XXXX년생" 패턴 우선 탐색
    m = re.search(r"(19[0-9]{2}|20[0-9]{2})\s*년\s*생", text)
    if not m:
        # 2) 그냥 "XXXX년" 패턴만이라도
        m = re.search(r"(19[0-9]{2}|20[0-9]{2})\s*년", text)
    if not m:
        # 3) 그 외 4자리 숫자만 있는 경우 (조금 느슨하게)
        m = re.search(r"\b(19[0-9]{2}|20[0-9]{2})\b", text)
    if not m:
        return None

    year = int(m.group(1))
    # 너무 앞/뒤의 말도 안 되는 년도는 버리기
    if year < 1900 or year > 2100:
        return None
    return year


def compute_pension_age(birth_year: int) -> int:
    """
    출생연도별 국민연금 노령연금 지급 개시 연령(만 나이)을 계산.

    1952년 이전: 60세
    1953~1956년생: 61세
    1957~1960년생: 62세
    1961~1964년생: 63세
    1965~1968년생: 64세
    1969년 이후: 65세
    """
    if birth_year <= 1952:
        return 60
    elif 1953 <= birth_year <= 1956:
        return 61
    elif 1957 <= birth_year <= 1960:
        return 62
    elif 1961 <= birth_year <= 1964:
        return 63
    elif 1965 <= birth_year <= 1968:
        return 64
    else:
        return 65


def build_pension_message(text: str) -> str:
    """
    음성에서 변환된 텍스트를 받아,
    - 출생연도를 찾고
    - 그에 따른 국민연금 수령 시작 나이를 계산해서

    결과확인 화면/answer_core 에 넣을 한 줄 안내 문장을 생성한다.

    예)
      입력: "나 1938년생인데 연금 언제부터 받을 수 있을까?"
      출력: "1938년생이시라면 국민연금은 만 60세부터 받으실 수 있습니다. 
             정확한 수급 시기와 예상 금액은 국민연금공단(1355)이나 주민센터에서 한 번 더 확인해 주세요."
    """
    year = extract_birth_year(text)
    if year is None:
        # 출생연도를 못 뽑으면 빈 문자열 → minwon_engine 쪽에서 기본 문구로 fallback
        return ""

    age = compute_pension_age(year)

    # 메인 한 줄 메시지
    main = (
        f"{year}년생이시라면 만 {age}세부터 받으실 수 있습니다. "
        "정확한 수급 시기와 예상 금액은 국민연금공단 고객센터(1355)로 확인해주세요."
    )

    return main
