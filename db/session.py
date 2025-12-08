# db/session.py
# -*- coding: utf-8 -*-
"""
SQLAlchemy 세션/엔진 설정 모듈

- 기본: .env 에 MySQL 접속 정보가 모두 있으면 MySQL 사용
- fallback: MySQL 정보가 없으면 자동으로 SQLite 파일(minwon_dev.db) 사용
- USE_DB 환경변수로 "논리적인" NO_DB_MODE 플래그를 제공
    - 라우터에서 DB를 실제로 쓸지 말지 분기할 때 사용 (엔진 생성은 항상 됨)
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ---------------------------------------------------------
# 1) 환경 변수 읽기
# ---------------------------------------------------------

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 로그 확인용 / 디버깅용
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

# 로컬/데모 모드에서 "논리적으로" DB를 쓰지 않는 플래그
#   - 실제로는 엔진/세션은 만들어지지만,
#   - 라우터(예: complaints/create) 쪽에서 USE_DB 를 보고
#     아예 INSERT/UPDATE 를 안 하게 분기할 수 있음.
USE_DB = os.getenv("USE_DB", "true").lower() == "true"

# ---------------------------------------------------------
# 2) MySQL or SQLite Fallback 결정
# ---------------------------------------------------------

# MySQL 연결 정보가 모두 있으면 MySQL 우선
if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME:
    DB_BACKEND = "mysql"
    DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
else:
    # 그 외에는 자동으로 SQLite 로 떨어진다.
    #   - 로컬 개발/테스트에서도 DB 없이 최소한의 기능은 돌릴 수 있게 하기 위함
    DB_BACKEND = "sqlite"
    SQLITE_PATH = os.getenv("SQLITE_PATH", "./minwon_dev.db")
    # 상대 경로를 절대경로로 풀어두면 헷갈림이 줄어듦
    SQLITE_PATH = os.path.abspath(SQLITE_PATH)
    DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

# ---------------------------------------------------------
# 3) SQLAlchemy Engine / SessionLocal / Base 생성
# ---------------------------------------------------------

engine_kwargs = {
    "echo": DB_ECHO,
    "future": True,
}

# SQLite 는 check_same_thread 옵션을 넣어줘야 FastAPI 멀티스레드 환경에서 안전
if DB_BACKEND == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # MySQL 의 경우 커넥션 재활용 옵션을 주는 편이 안전
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)

# 대부분의 프로젝트에서 models 모듈이 이 Base 를 import 해서 사용
Base = declarative_base()

# ---------------------------------------------------------
# 4) FastAPI Depends 에서 쓸 get_db
# ---------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의 Depends 에서 사용하는 DB 세션 의존성.

    예:
        from db.session import get_db

        @router.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...

    - USE_DB 가 False 라도 세션 자체는 반환된다.
      (라우터 쪽에서 USE_DB 플래그를 보고 실제 DB 작업을 건너뛸지 결정)
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
