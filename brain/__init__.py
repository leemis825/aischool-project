# -*- coding: utf-8 -*-
"""
brain 패키지

고령층 민원 키오스크에서 사용하는 "민원 분류·안내 엔진"의 핵심 로직 모음입니다.

외부(예: app_fastapi.py)에서는 보통 아래 함수만 직접 사용합니다.

- run_pipeline_once(text, history):
    한 번의 민원 텍스트를 받아
    카테고리 분류, 위험도/현장 출동 여부 판단,
    주민 안내용 멘트(user_facing)와
    담당자용 요약(staff_payload)을 한 번에 생성합니다.

세부 로직은 다음 모듈로 나뉘어 있습니다.

- utils_text      : 텍스트 정규화, 위험 키워드, 키워드 추출 등 공통 유틸
- rules_pension   : 출생연도별 연금 개시 연령/안내 문구
- llm_client      : OpenAI Chat/Whisper 호출 래퍼
- classifier      : 카테고리/위험도/현장 출동 필요 여부 분류
- summarizer      : 주민용·담당자용 요약 생성
- handling        : simple_guide / contact_only / official_ticket 결정
- builders        : user_facing / staff_payload 형태로 결과 조립
- text_session_state, turn_router : 멀티턴 대화/이슈 A,B,C 관리
"""

from .minwon_engine import run_pipeline_once

__all__ = ["run_pipeline_once"]
