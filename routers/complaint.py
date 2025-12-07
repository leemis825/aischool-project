# routers/complaint.py
# -*- coding: utf-8 -*-

"""
민원 저장/조회/업데이트 라우터

- /complaints/create
    STT+민원엔진 결과를 session_id 기준으로 upsert
    (로컬 NO_DB_MODE 에서는 DB 저장 없이 OK 반환)

- /complaints/{session_id}
    특정 세션의 민원 및 대화 메시지 조회
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from db.session import get_db, USE_DB
from db.models.complaint import Complaint
from db.models.complaint_message import ComplaintMessage
from pydantic import BaseModel, Field


router = APIRouter(prefix="/complaints", tags=["complaints"])


# ---------------------------------------------------------
# Pydantic 입력 스키마
# ---------------------------------------------------------

class ComplaintCreate(BaseModel):
    session_id: str = Field(..., description="민원 세션 ID")
    user_id: Optional[str] = Field(None, description="사용자/장비 ID")
    title: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None

    category: Optional[str] = None          # staff_payload.category
    minwon_type: Optional[str] = None
    handling_type: Optional[str] = None

    risk_level: Optional[str] = None
    needs_visit: Optional[bool] = None
    citizen_request: Optional[str] = None
    location: Optional[str] = None

    engine_result: Optional[Dict[str, Any]] = None  # (프론트 저장용)


class ComplaintMessageCreate(BaseModel):
    session_id: str
    sender: str               # "user" | "agent"
    text: str                 # 원문 STT 결과 또는 LLM 답변
    stage: Optional[str] = "" # classification | guide | handoff | clarification


# ---------------------------------------------------------
# 1) 민원 저장 (session_id 기준 upsert)
# ---------------------------------------------------------

@router.post("/create")
def create_or_update_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
):
    """
    STT+민원엔진 결과를 DB에 저장하거나(No DB 모드면 패스)
    session_id 기준으로 1건 유지 (upsert).
    """
    # -------------------------------------------
    # 🔥 NO_DB_MODE: 로컬/테스트에서는 DB 저장 없이 통과
    # -------------------------------------------
    if not USE_DB:
        print("\n[NO_DB_MODE] /complaints/create received payload:")
        print(payload.dict())
        return {
            "status": "ok",
            "id": None,
            "mode": "no_db",
            "session_id": payload.session_id,
        }

    # -------------------------------------------
    # 🔥 실제 DB 저장 로직
    # -------------------------------------------

    # 기존 민원 조회 (세션 기준)
    complaint = (
        db.query(Complaint)
        .filter(Complaint.session_id == payload.session_id)
        .first()
    )

    # 신규 생성
    if complaint is None:
        complaint = Complaint(
            user_id=payload.user_id,
            session_id=payload.session_id,
            title=payload.title,
            raw_text=payload.raw_text,
            summary=payload.summary,

            category=payload.category or payload.minwon_type,
            minwon_type=payload.minwon_type,
            handling_type=payload.handling_type,
            risk_level=payload.risk_level,

            needs_visit=payload.needs_visit if payload.needs_visit is not None else False,
            citizen_request=payload.citizen_request,
            location=payload.location,
        )
        db.add(complaint)
        db.flush()  # id 생성

    # 기존 민원 업데이트 (upsert)
    else:
        if payload.title:
            complaint.title = payload.title
        if payload.raw_text:
            complaint.raw_text = payload.raw_text
        if payload.summary:
            complaint.summary = payload.summary
        if payload.category:
            complaint.category = payload.category
        if payload.minwon_type:
            complaint.minwon_type = payload.minwon_type
        if payload.handling_type:
            complaint.handling_type = payload.handling_type
        if payload.risk_level:
            complaint.risk_level = payload.risk_level

        # needs_visit은 명시적으로 전달되면 업데이트
        if payload.needs_visit is not None:
            complaint.needs_visit = payload.needs_visit

        if payload.citizen_request:
            complaint.citizen_request = payload.citizen_request
        if payload.location:
            complaint.location = payload.location

    db.commit()
    db.refresh(complaint)

    return {
        "status": "ok",
        "id": complaint.id,
        "session_id": complaint.session_id,
        "mode": "db",
    }


# ---------------------------------------------------------
# 2) 민원 메시지 저장
# ---------------------------------------------------------

@router.post("/message")
def create_message(
    payload: ComplaintMessageCreate,
    db: Session = Depends(get_db),
):
    if not USE_DB:
        print("\n[NO_DB_MODE] /complaints/message received payload:")
        print(payload.dict())
        return {"status": "ok", "id": None, "mode": "no_db"}

    message = ComplaintMessage(
        session_id=payload.session_id,
        sender=payload.sender,
        text=payload.text,
        stage=payload.stage,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return {"status": "ok", "id": message.id}


# ---------------------------------------------------------
# 3) 특정 세션의 모든 민원 및 메시지 조회
# ---------------------------------------------------------

@router.get("/{session_id}")
def get_complaint(session_id: str, db: Session = Depends(get_db)):
    if not USE_DB:
        return {"status": "no_db", "session_id": session_id, "detail": "NO_DB_MODE enabled"}

    complaint = (
        db.query(Complaint)
        .filter(Complaint.session_id == session_id)
        .first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    messages = (
        db.query(ComplaintMessage)
        .filter(ComplaintMessage.session_id == session_id)
        .order_by(ComplaintMessage.id.asc())
        .all()
    )

    return {
        "status": "ok",
        "complaint": complaint,
        "messages": messages,
    }
