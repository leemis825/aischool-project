# -*- coding: utf-8 -*-
"""
text_session_state.py

텍스트 기반 멀티턴 민원에서
- Clarification(추가 위치 질문) 처리
- 민원 이슈(A, B, C...) 단위 관리
- 이번 발화가 기존 이슈의 후속인지/새 이슈인지 라우팅

을 담당하는 상태 관리 모듈입니다.

🎯 주요 역할
--------------------------------------
1) build_effective_text(user_raw)
   - 바로 이전 턴이 stage == "clarification" 이면
     → 이전 문장 + "추가 위치 정보: ..." 형태로 붙여서 반환

2) register_turn(user_raw, effective_text, engine_result)
   - 민원 엔진 결과를 바탕으로
     - 어떤 이슈(A/B/...)에 속하는지 결정
       · active_issue_id가 있으면 → 그대로 사용
       · 없으면 → brain.turn_router.choose_issue_for_followup 사용
       · 아무 이슈에도 안 맞으면 → 새 이슈 생성
     - clarification 이면 이슈는 open 유지, 다음 턴을 위해 pending_text 저장
     - guide/handoff 등이면 이슈 closed, active_issue_id 초기화

3) debug_issues()
   - 현재 이슈/턴 상태를 JSON 직렬화 가능한 dict로 반환
   - main.py에서 디버깅 출력용으로 사용
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from brain.turn_router import choose_issue_for_followup


# ---------------------------------------------------------
# 데이터 구조 정의
# ---------------------------------------------------------

@dataclass
class Turn:
    """
    한 번의 사용자 발화 + 엔진 결과를 나타내는 단위.
    """
    id: int
    raw_text: str
    effective_text: str
    engine_result: Dict[str, Any]
    issue_id: str  # A, B, C ...


@dataclass
class Issue:
    """
    민원 이슈 단위.
    예: A = "우리집 앞 나무 쓰러짐", B = "마을회관 앞 쓰레기"
    """
    id: str
    status: str = "open"  # "open" | "closed"
    turns: List[int] = field(default_factory=list)

    category: Optional[str] = None
    location: str = ""
    risk_level: str = "보통"
    needs_visit: bool = False

    # 이 이슈를 대표하는 한 줄 요약 (가장 최근 effective_text 기준)
    brief: str = ""


# ---------------------------------------------------------
# 메인 클래스
# ---------------------------------------------------------

class TextSessionState:
    """
    텍스트 모드에서 멀티턴 민원 상태를 관리하는 클래스.

    - 한 세션 안에 여러 이슈(A/B/...)가 존재할 수 있음
    - Clarification인 경우, 다음 턴에서 문장을 합쳐서 엔진에 보냄
    - 이슈 간 라우팅은 brain.turn_router의 LLM을 사용
    """

    def __init__(self):
        # 전체 턴 목록 (id는 1부터 증가)
        self.turns: List[Turn] = []

        # 이슈 목록: {"A": Issue(...), "B": Issue(...)}
        self.issues: Dict[str, Issue] = {}

        # 현재 clarification 진행 중인 이슈 id (없으면 None)
        self.active_issue_id: Optional[str] = None

        # 직전 턴이 clarification 이었을 때,
        # "기본이 되는 문장"을 저장 (다음 입력과 합치기 용도)
        self._pending_clarification_text: Optional[str] = None

        # A, B, C ... 발급용 카운터
        self._issue_counter: int = 0

    # -----------------------------------------------------
    # 이슈 ID 발급
    # -----------------------------------------------------

    def _new_issue_id(self) -> str:
        """
        이슈 ID를 A, B, C, ... 순서로 발급.
        Z를 넘어갈 일은 거의 없겠지만, 넘어가면 AA, AB... 식으로 늘릴 수도 있음.
        """
        idx = self._issue_counter
        self._issue_counter += 1
        # 간단히 A~Z까지만 가정
        return chr(ord("A") + idx)

    # -----------------------------------------------------
    # Clarification 결합용 텍스트 생성
    # -----------------------------------------------------

    def build_effective_text(self, user_raw: str) -> str:
        """
        직전 턴이 clarification이면,
        이전 문장 + "추가 위치 정보: {user_raw}"를 합쳐서 반환.

        그렇지 않으면 user_raw 그대로 반환.
        """
        if self._pending_clarification_text:
            base = self._pending_clarification_text
            return f"{base} 추가 위치 정보: {user_raw}"
        return user_raw

    # -----------------------------------------------------
    # 턴 등록 + 이슈 라우팅
    # -----------------------------------------------------

    def register_turn(
        self,
        user_raw: str,
        effective_text: str,
        engine_result: Dict[str, Any],
    ) -> Turn:
        """
        민원 엔진 결과를 받아:
        - 어떤 이슈에 속하는지 결정
        - Issue/Turn 상태 갱신
        - clarification 상태 갱신

        반환값: 생성된 Turn 객체
        """
        turn_id = len(self.turns) + 1

        stage = engine_result.get("stage")
        category = engine_result.get("minwon_type")
        staff_payload = engine_result.get("staff_payload", {}) or {}

        location = staff_payload.get("location", "") or ""
        risk_level = staff_payload.get("risk_level", "보통")
        needs_visit = bool(staff_payload.get("needs_visit", False))

        # -----------------------------
        # 0) 라우터에 넘길 이슈 요약 정보 구성
        # -----------------------------
        router_issues: Dict[str, dict] = {}
        for issue_id, iss in self.issues.items():
            router_issues[issue_id] = {
                "status": iss.status,
                "category": iss.category,
                "brief": iss.brief or "",
            }

        # -----------------------------
        # 1) 이번 턴이 속할 issue_id 결정
        # -----------------------------
        issue_id: Optional[str]

        if self.active_issue_id is not None:
            # 이미 clarification 등으로 진행 중인 이슈가 있으면 그대로 사용
            issue_id = self.active_issue_id
        else:
            # 진행 중인 이슈가 없고, 기존 이슈는 있을 때 → LLM 라우터 사용
            if router_issues:
                chosen = choose_issue_for_followup(
                    current_text=user_raw,
                    issues_for_router=router_issues,
                )
            else:
                chosen = None

            if chosen is not None:
                issue_id = chosen
                self.active_issue_id = chosen
            else:
                # 어느 이슈와도 연관성이 애매 → 새 이슈 생성
                issue_id = self._new_issue_id()
                self.issues[issue_id] = Issue(
                    id=issue_id,
                    status="open",
                    category=category,
                    location=location,
                    risk_level=risk_level,
                    needs_visit=needs_visit,
                    brief=effective_text[:80],
                )
                self.active_issue_id = issue_id

        # -----------------------------
        # 2) 이슈 정보 갱신
        # -----------------------------
        issue = self.issues[issue_id]
        issue.turns.append(turn_id)

        if category:
            issue.category = category
        if location:
            issue.location = location
        issue.risk_level = risk_level
        issue.needs_visit = needs_visit
        issue.brief = effective_text[:80]

        # -----------------------------
        # 3) 턴 객체 생성/저장
        # -----------------------------
        turn = Turn(
            id=turn_id,
            raw_text=user_raw,
            effective_text=effective_text,
            engine_result=engine_result,
            issue_id=issue_id,
        )
        self.turns.append(turn)

        # -----------------------------
        # 4) Clarification 상태 업데이트
        # -----------------------------
        if stage == "clarification":
            # 다음 입력에서 문장 합치기를 위해 저장
            self._pending_clarification_text = effective_text
            issue.status = "open"
        else:
            # 이 이슈는 일단 한 번 마무리된 것으로 간주
            self._pending_clarification_text = None
            issue.status = "closed"
            self.active_issue_id = None

        return turn

    # -----------------------------------------------------
    # 디버그용 뷰
    # -----------------------------------------------------

    def debug_issues(self) -> Dict[str, Any]:
        """
        main.py에서 print 하기 좋은 형태로
        현재 이슈/턴 상태를 딕셔너리로 반환.
        """
        issues_view: Dict[str, Any] = {}
        for issue_id, iss in self.issues.items():
            issues_view[issue_id] = {
                "status": iss.status,
                "category": iss.category,
                "location": iss.location,
                "risk_level": iss.risk_level,
                "needs_visit": iss.needs_visit,
                "brief": iss.brief,
                "turn_ids": iss.turns,
            }

        return {
            "total_turns": len(self.turns),
            "issues": issues_view,
        }
