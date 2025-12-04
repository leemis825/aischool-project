from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.session import get_db
from db.models.user import User
from db.models.complaint import Complaint
from routers.admin_user import get_current_admin, AdminUser

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])

@router.get("/summary")
def get_dashboard_summary(
    current_admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_complaints = db.query(func.count(Complaint.id)).scalar() or 0

    today = date.today()
    today_complaints = (
        db.query(func.count(Complaint.id))
        .filter(func.date(Complaint.created_at) == today)   # created_at 컬럼 있다고 가정
        .scalar()
        or 0
    )

    resolved_complaints = (
        db.query(func.count(Complaint.id))
        .filter(Complaint.status == "resolved")
        .scalar()
        or 0
    )

    # ✅ 미처리 민원 수 = 전체 - 처리완료
    unresolved_complaints = total_complaints - resolved_complaints
    return {
        "total_users": total_users,
        "total_complaints": total_complaints,
        "today_complaints": today_complaints,
        "unresolved_complaints": unresolved_complaints,
        "resolved_complaints" : resolved_complaints
    }
