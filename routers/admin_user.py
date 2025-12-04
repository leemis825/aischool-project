from datetime import datetime, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import cast
import bcrypt

from db.session import get_db
from db.models.admin_user import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

#Authorization 헤더에서 Bearer 토큰을 자동으로 추출
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

# 📦 로그인 요청 바디
class LoginRequest(BaseModel):
    username: str
    password: str


# 📦 로그인 응답(토큰)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(plain_password: str) -> str:
    """비밀번호 문자열을 bcrypt 해시로 변환"""
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")



def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력한 비밀번호와 저장된 해시를 비교"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # 해시 형식이 잘못된 경우 등
        return False
    

# 🎫 토큰 생성 함수
def create_access_token(admin_id: int) -> str:
    """관리자 ID를 담은 JWT access_token 생성"""
    now = datetime.utcnow()
    expire = now + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(admin_id),  # 토큰 주체(관리자 ID)
        "iat": now,
        "exp": expire,
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


# 👤 현재 로그인된 관리자 가져오기 (보호된 API에서 사용)
async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    credentials_exception = HTTPException(
        status_code=401,
        detail="인증에 실패했습니다. 다시 로그인 해주세요.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        admin_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    admin = (
        db.query(AdminUser)
        .filter(AdminUser.id == admin_id)
        .first()
    )
    if admin is None:
        raise credentials_exception

    return admin

# 관리자 생성은 내가 직접하는 걸로. 그래서 일단 뺌.

# 🔑 로그인: 성공 시 JWT 토큰 발급
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    1) username 으로 관리자 조회
    2) bcrypt로 비밀번호 검증
    3) 성공 시 JWT access_token 발급
    """
    user = (
        db.query(AdminUser)
       .filter(AdminUser.username == body.username)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )
    hashed_pw = cast(str, user.password_hash)

    if not verify_password(body.password, hashed_pw):
        raise HTTPException(
            status_code=400,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )
    access_token = create_access_token(int(user.id))
    return TokenResponse(access_token=access_token)


# 🧪 내 정보 확인 (JWT 잘 작동하는지 테스트용)
@router.get("/me")
async def read_me(current_admin: AdminUser = Depends(get_current_admin)):
    return {
        "id": current_admin.id,
        "username": current_admin.username,
        "role": current_admin.role,
    }

