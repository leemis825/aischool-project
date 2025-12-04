from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from db.models.user import User

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/create")
def create_user(name: str, phone: str, db: Session = Depends(get_db)):
    user = User(name=name, phone=phone)
    db.add(user)
    db.commit()
    return {"status": "ok", "id": user.id}

@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    return db.query(User).filter(User.id == user_id).first()

@router.get("/")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
