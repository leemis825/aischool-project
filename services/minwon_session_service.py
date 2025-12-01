# services/minwon_session_service.py
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from models import MinwonSession


def upsert_minwon_session(
    db: Session,
    session_id: str,
    text_raw: str,
    engine_result: Dict[str, Any],
    status: str = "in_progress",
) -> MinwonSession:
    """
    민원 엔진 결과를 기반으로 minwon_session 테이블에
    신규 생성 또는 업데이트(upsert) 한다.
    - session_id: 프론트에서 쓰는 세션 ID (uuid 문자열)
    - text_raw: 사용자가 말한 원문 텍스트
    - engine_result: minwon_engine 이 반환한 JSON(dict)
    """

    # 1) 엔진 결과에서 우리가 저장할 값 뽑기
    minwon_type: str = engine_result.get("minwon_type", "기타")
    handling_type: str = engine_result.get("handling_type", "simple_guide")
    stage: str = engine_result.get("stage", "")
    risk_level: str = "보통"

    # risk_level 은 staff_payload 쪽에 있을 수도 있음
    staff_payload: Optional[Dict[str, Any]] = engine_result.get("staff_payload")
    if staff_payload and isinstance(staff_payload, dict):
        risk_level = staff_payload.get("risk_level", risk_level)

    # 2) 기존 세션이 있나 확인
    session_obj: Optional[MinwonSession] = db.get(MinwonSession, session_id)

    now = datetime.utcnow()

    if session_obj is None:
        # 처음 생성되는 세션
        session_obj = MinwonSession(
            session_id=session_id,
            received_at=now,
            text_raw=text_raw,
            minwon_type=minwon_type,
            risk_level=risk_level,
            handling_type=handling_type,
            status=status,
        )
        db.add(session_obj)
    else:
        # 이미 있으면 최신 값으로 업데이트
        session_obj.text_raw = text_raw  # 마지막 발화로 덮어쓸지, 처음 것 유지할지는 정책에 따라
        session_obj.minwon_type = minwon_type
        session_obj.risk_level = risk_level
        session_obj.handling_type = handling_type
        session_obj.status = status

    db.commit()
    db.refresh(session_obj)
    return session_obj
