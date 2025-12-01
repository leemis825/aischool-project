# -*- coding: utf-8 -*-
"""
brain.engine_pipeline

민원 텍스트 엔진의 "전체 흐름"만 모아놓은 설계도 역할의 모듈입니다.

실제 엔트리 포인트는 minwon_engine.run_pipeline_once 이고,
그 안에서 이 모듈의 함수들을 호출해서 파이프라인을 구성하도록 할 수 있습니다.

예상 역할(설계 관점):

1. 사전 전처리
   - normalize(text), split_additional_location(text)

2. 규칙/LLM 기반 분류 단계
   - rule_first_classify(text)
   - llm_classify_category_and_fieldwork(...)

3. 처리 방식 결정
   - decide_handling_from_struct(...)

4. 요약 및 결과 조립
   - summarize_for_user / summarize_for_staff
   - build_user_facing / build_staff_payload

※ 현재 프로젝트에서는 minwon_engine 안에 run_pipeline_once가 있기 때문에,
   이 파일은 "파이프라인 구조를 더 잘게 나누고 싶을 때" 확장용으로 사용합니다.
"""
