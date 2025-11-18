# -*- coding: utf-8 -*-
"""
session_state.py

음성 기반 멀티턴 민원 시스템에서
- 대화 세션(conversation)
- 화자(speaker)
단위로 상태를 관리하는 모듈입니다.

🎯 역할 요약
--------------------------------------
1. 세션 생성 / 관리
2. pyannote.audio가 구분한 speaker_id 별 정보 저장
3. 각 speaker별:
   - turn_id 증가
   - history 저장
   - 마지막 위치(last_location)
   - 마지막 카테고리(last_category)
   - 텍스트 멀티턴 엔진용 TextSessionState(text_state)
4. minwon_engine 결과를 기반으로 speaker_state 갱신

👉 핵심 포인트:
이 모듈은 '음성 처리 레이어(speaker)'의 중심이며,
minwon_engine.py는 오직 "텍스트 내용"만 처리합니다.
"""

import uuid
from typing import Dict, Any, List

from brain.text_session_state import TextSessionState


class SessionState:
    """
    전체 키오스크 대화 상태를 관리하는 클래스.
    여러 대화 세션이 동시에 가능하도록 설계되어 있습니다.
    """

    def __init__(self):
        # 구조:
        # sessions = {
        #   "session_id": {
        #       "speakers": {
        #           "SPEAKER_00": {
        #               "turn": 1,
        #               "history": [...],
        #               "last_location": None,
        #               "last_category": None,
        #               "text_state": TextSessionState()
        #           }
        #       }
        #   }
        # }
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------
    # 세션 관리
    # ---------------------------------------------------------

    def start_session(self) -> str:
        """
        새로운 대화를 하나 시작하고 session_id를 반환합니다.
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {"speakers": {}}
        return session_id

    def ensure_session(self, session_id: str):
        """
        해당 세션이 없으면 자동 생성합니다.
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {"speakers": {}}

    # ---------------------------------------------------------
    # 화자 관리
    # ---------------------------------------------------------

    def ensure_speaker(self, session_id: str, speaker_id: str):
        """
        세션 내 특정 화자의 상태가 없으면 자동 생성합니다.
        """
        self.ensure_session(session_id)
        speakers = self.sessions[session_id]["speakers"]
        if speaker_id not in speakers:
            speakers[speaker_id] = {
                "turn": 0,
                "history": [],
                "last_location": None,
                "last_category": None,
                # 텍스트 멀티턴 엔진(TextSessionState)을 화자별로 하나씩 보유
                "text_state": TextSessionState(),
            }

    def next_turn(self, session_id: str, speaker_id: str) -> int:
        """
        세션/화자별 turn_id를 1 증가시키고 반환합니다.
        """
        self.ensure_speaker(session_id, speaker_id)
        speakers = self.sessions[session_id]["speakers"]
        speakers[speaker_id]["turn"] += 1
        return speakers[speaker_id]["turn"]

    # ---------------------------------------------------------
    # 상태 조회
    # ---------------------------------------------------------

    def get_history(self, session_id: str, speaker_id: str) -> List[Dict[str, Any]]:
        """
        특정 화자의 이전 발화 기록(history)을 반환합니다.
        """
        self.ensure_speaker(session_id, speaker_id)
        return self.sessions[session_id]["speakers"][speaker_id]["history"]

    def get_last_location(self, session_id: str, speaker_id: str):
        self.ensure_speaker(session_id, speaker_id)
        return self.sessions[session_id]["speakers"][speaker_id]["last_location"]

    def get_last_category(self, session_id: str, speaker_id: str):
        self.ensure_speaker(session_id, speaker_id)
        return self.sessions[session_id]["speakers"][speaker_id]["last_category"]

    def get_text_state(self, session_id: str, speaker_id: str) -> TextSessionState:
        """
        특정 화자에 연결된 TextSessionState를 반환합니다.
        (멀티턴 민원 엔진과 동일한 로직을 음성에도 적용하기 위함)
        """
        self.ensure_speaker(session_id, speaker_id)
        return self.sessions[session_id]["speakers"][speaker_id]["text_state"]

    # ---------------------------------------------------------
    # 상태 업데이트 (민원 엔진 결과 기반)
    # ---------------------------------------------------------

    def update_state(self,
                     session_id: str,
                     speaker_id: str,
                     engine_result: Dict[str, Any],
                     user_text: str):
        """
        minwon_engine의 결과(JSON)를 화자 상태에 반영합니다.

        - history 추가
        - 위치(location) 업데이트
        - 카테고리(minwon_type) 업데이트
        """
        self.ensure_speaker(session_id, speaker_id)
        sp = self.sessions[session_id]["speakers"][speaker_id]

        # 1) history 로그 기록
        sp["history"].append({
            "turn": sp["turn"],
            "text": user_text,
            "engine_output": engine_result,
        })

        # 2) 위치 업데이트 (요약 데이터에 위치가 있을 경우)
        new_loc = engine_result.get("staff_payload", {}).get("location")
        if new_loc and isinstance(new_loc, str) and len(new_loc.strip()) > 0:
            sp["last_location"] = new_loc.strip()

        # 3) 카테고리 업데이트
        new_cat = engine_result.get("minwon_type")
        if new_cat:
            sp["last_category"] = new_cat

    # ---------------------------------------------------------
    # 디버깅용
    # ---------------------------------------------------------

    def debug_print(self):
        """
        세션 전체 상태를 보기 쉽게 출력하는 디버그 함수
        """
        import json
        print(json.dumps(self.sessions, indent=2, ensure_ascii=False))
