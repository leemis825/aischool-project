# -*- coding: utf-8 -*-
"""
brain.builders

분류/요약 결과를 실제로 프론트에서 사용하는 형태로
예쁘게 "포장"해 주는 역할을 담당합니다.

주요 기능(예시, 실제 구현에 따라 약간 달라질 수 있음):
- build_user_facing(...):
    주민에게 보여줄/읽어줄 정보 묶음 생성
    (short_title, main_message, next_action_guide,
     phone_suggestion, confirm_question,
     tts_listening, tts_summary, tts_result, answer_core).

- build_staff_payload(...):
    담당 공무원용 요약 정보 생성
    (summary, category, location, time_info, risk_level,
     needs_visit, citizen_request, raw_keywords, memo_for_staff).

분류/요약 단계에서 만들어진 구조화 데이터를 받아서
"프론트/담당자 눈높이에 맞는 최종 형태"로 조립하는 계층입니다.
"""
