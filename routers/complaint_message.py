from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from db.models.complaint_message import ComplaintMessage
from routers.admin_user import get_current_admin, AdminUser

router = APIRouter(prefix="/messages", tags=["messages"])

# 민원 메시지 생성
@router.post("/create")
def create_message(complaint_id: int, sender: str, content: str, db: Session = Depends(get_db)):
    msg = ComplaintMessage(
        complaint_id=complaint_id,
        sender=sender,   # 'user' / 'admin'
        content=content
    )
    db.add(msg)
    db.commit()
    return {"status": "ok", "id": msg.id}

# 민원별 메시지 조회
@router.get("/complaint/{complaint_id}")
def get_messages(
    complaint_id: int,
    current_admin: AdminUser = Depends(get_current_admin),   
    db: Session = Depends(get_db),
):
    return (
        db.query(ComplaintMessage)
        .filter(ComplaintMessage.complaint_id == complaint_id)
        .all()
    )