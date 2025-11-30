# routers/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/", summary="헬스 체크", tags=["health"])
def root():
    return {"message": "간편민원접수 FastAPI 동작 중"}
