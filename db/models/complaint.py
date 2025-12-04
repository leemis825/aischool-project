from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.base import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    raw_text = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="new")
    location = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    resolved_at = Column(DateTime, nullable=True)
    minwon_type = Column(String(50), nullable=True)      # 도로/치안/복지 등
    handling_type = Column(String(50), nullable=True)    # official_ticket 등
    risk_level = Column(String(20), nullable=True)       # '긴급', '보통' 등
    needs_visit = Column(Boolean, nullable=False, default=False)
    citizen_request = Column(Text, nullable=True)        # "쓰러진 나무 치워 달라"
    summary = Column(Text, nullable=True)                # 직원용 요약
    phone_number = Column(String(20), nullable=True)

    # 관계들
    user = relationship(
        "User",
        back_populates="complaints",
    )
    messages = relationship(
        "ComplaintMessage",
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
