from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from typing import Literal

from db.session import get_db
from db.models.complaint import Complaint
from db.models.user import User
from db.models.complaint_message import ComplaintMessage  # 🔹 메시지용 모델 import
from routers.admin_user import get_current_admin, AdminUser
from db.models.complaint_message import ComplaintMessage

from fastapi import APIRouter, Depends, HTTPException

class ComplaintCreate(BaseModel):
    # 🔹 키오스크면 대부분 None, 웹 로그인 붙이면 user_id 채워서 보내면 됨
    user_id: Optional[int] = None

    # 🔹 민원 세션 (STT에서 받은 session_id)
    session_id: str

    # Complaint(민원 헤더)에 들어갈 정보들
    title: Optional[str] = None
    raw_text: Optional[str] = None
    category: Optional[str] = None

    minwon_type: Optional[str] = None
    handling_type: Optional[str] = None
    risk_level: Optional[str] = None
    needs_visit: Optional[bool] = None
    citizen_request: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None

    # 🔹 이번 턴 대화 내용 (ComplaintMessage 용)
    stt_text: Optional[str] = None        # 시민이 이번에 말한 문장
    bot_answer: Optional[str] = None      # 봇이 안내한 문장
    audio_url: Optional[str] = None       # 원본 음성 파일 경로/URL (있으면)
    tts_audio_url: Optional[str] = None   # TTS 음성 파일 경로/URL (있으면)

class ComplaintPhoneUpdate(BaseModel):
    session_id: str
    phone_number: str

class ComplaintReplyCreate(BaseModel):
    content: str


class ComplaintStatusUpdate(BaseModel):
    status: Literal["new", "in_progress", "resolved"]



router = APIRouter(prefix="/complaints", tags=["complaints"])



# 🔄 민원 생성/업데이트 (session_id 기준 upsert + 대화 로그 저장)
@router.post("/create")
def create_or_update_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
):
    """
    - 같은 session_id 로 호출되면 같은 Complaint 에 붙음
    - 처음 보는 session_id 면 Complaint 를 새로 생성
    - 매 호출마다 ComplaintMessage(대화 로그)를 남김
    """

    # 1) session_id 로 기존 민원 조회
    complaint = (
        db.query(Complaint)
        .filter(Complaint.session_id == payload.session_id)
        .first()
    )

    # 2) 없으면 새 민원 생성
    if complaint is None:
        complaint = Complaint(
            user_id=payload.user_id,
            session_id=payload.session_id,
            title=payload.title,
            raw_text=payload.raw_text,
            category=payload.category or payload.minwon_type,
            minwon_type=payload.minwon_type,
            handling_type=payload.handling_type,
            risk_level=payload.risk_level,
            needs_visit=payload.needs_visit if payload.needs_visit is not None else False,
            citizen_request=payload.citizen_request,
            summary=payload.summary,
            location=payload.location,
        )
        db.add(complaint)
        db.flush()  # complaint.id 확보
    

    # 3) 이번 턴 대화 로그 저장 (user / bot)
    if payload.stt_text:
        user_msg = ComplaintMessage(
            complaint_id=complaint.id,
            role="user",
            content=payload.stt_text,   # ⬅️ stt_text → content
            audio_url=payload.audio_url,
        )
        db.add(user_msg)

    if payload.bot_answer:
        bot_msg = ComplaintMessage(
            complaint_id=complaint.id,
            role="bot",
            content=payload.bot_answer,  # ⬅️ bot_answer → content
            tts_audio_url=payload.tts_audio_url,
        )
        db.add(bot_msg)


    db.commit()
    db.refresh(complaint)

    return {
        "status": "ok",
        "id": complaint.id,
        "session_id": complaint.session_id,
    }


@router.post("/set-phone")
def set_complaint_phone(
    payload: ComplaintPhoneUpdate,
    db: Session = Depends(get_db),
):
    """
    - 키오스크에서 전화번호 입력 후 호출
    - session_id 로 해당 Complaint 를 찾아 phone_number 업데이트
    """
    complaint = (
        db.query(Complaint)
        .filter(Complaint.session_id == payload.session_id)
        .first()
    )

    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.phone_number = payload.phone_number
    db.commit()
    db.refresh(complaint)

    return {"status": "ok", "id": complaint.id}

# 민원 단건 조회
@router.get("/{complaint_id}")
def get_complaint(
    complaint_id: int,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )


# 특정 유저의 민원 목록
@router.get("/user/{user_id}")
def get_user_complaints(
    user_id: int,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return db.query(Complaint).filter(Complaint.user_id == user_id).all()


# 📌 민원 목록 (페이지네이션)
@router.get("/")
def list_complaints(
    page: int = 1,
    page_size: int = 10,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # 전체 개수
    total = db.query(func.count(Complaint.id)).scalar() or 0

    # 페이지에 해당하는 row들
    offset = (page - 1) * page_size

    rows = (
        db.query(
            Complaint.id,
            Complaint.title,
            Complaint.category,
            Complaint.created_at,
            Complaint.status,
            Complaint.phone_number,
            Complaint.risk_level
        )
        .outerjoin(User, Complaint.user_id == User.id)  # 🔹 user_id가 NULL인 민원도 포함
        .order_by(Complaint.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "created_at": r.created_at,
            "status": getattr(r, "status", "new"), 
            "location": getattr(r, "location", None),
            "phone_number": r.phone_number,
            "risk_level": r.risk_level,

        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.post("/{complaint_id}/read")
def mark_complaint_as_read(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()

    if not complaint:
        return {"status": "error", "message": "Complaint not found"}

    # 🔹 new → read 로 변경
    if complaint.status == "new":
        complaint.status = "read"

    db.commit()
    return {"status": "ok", "id": complaint_id, "updated_status": complaint.status}


@router.get("/detail/{complaint_id}")
def get_complaint_detail(
    complaint_id: int,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # 1) 민원 본문 조회
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # 2) 관련 메시지(대화 로그) 조회 - 시간순
    messages = (
        db.query(ComplaintMessage)
        .filter(ComplaintMessage.complaint_id == complaint_id)
        .order_by(ComplaintMessage.created_at.asc())
        .all()
    )

    complaint_dict = {
        "id": complaint.id,
        "session_id": getattr(complaint, "session_id", None),
        "title": complaint.title,
        "raw_text": getattr(complaint, "raw_text", None),
        "summary": getattr(complaint, "summary", None),
        "category": complaint.category,
        "minwon_type": getattr(complaint, "minwon_type", None),
        "handling_type": getattr(complaint, "handling_type", None),
        "risk_level": getattr(complaint, "risk_level", None),
        "needs_visit": getattr(complaint, "needs_visit", None),
        "citizen_request": getattr(complaint, "citizen_request", None),
        "location": getattr(complaint, "location", None),
        "phone_number": getattr(complaint, "phone_number", None),
        "status": getattr(complaint, "status", None),
        "created_at": complaint.created_at,
        "updated_at": getattr(complaint, "updated_at", None),
        "resolved_at": getattr(complaint, "resolved_at", None),
    }

    messages_list = [
        {
            "id": m.id,
            "role": m.role,            
            "content": m.content,
            "audio_url": m.audio_url,
            "tts_audio_url": m.tts_audio_url,
            "created_at": m.created_at,
        }
        for m in messages
    ]

    return {
        "complaint": complaint_dict,
        "messages": messages_list,
    }

@router.post("/{complaint_id}/reply")
def add_admin_reply(
    complaint_id: int,
    payload: ComplaintReplyCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    msg = ComplaintMessage(
        complaint_id=complaint.id,
        role="admin",
        content=payload.content,   # ✅ 관리자 답변도 content에
    )
    db.add(msg)

    db.commit()
    db.refresh(msg)

    return {"status": "ok", "message_id": msg.id}


@router.post("/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    payload: ComplaintStatusUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.status = payload.status
    db.commit()
    db.refresh(complaint)

    return {
        "status": "ok",
        "complaint_id": complaint.id,
        "new_status": complaint.status,
    }