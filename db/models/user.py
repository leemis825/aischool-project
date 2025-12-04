from sqlalchemy import Column, BigInteger, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    phone_encrypted = Column(Text, nullable=False)
    phone_last4 = Column(String(4), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # 하나의 사용자 → 여러 민원
    complaints = relationship(
        "Complaint",           # 문자열로 쓰면 import 순환 피할 수 있음
        back_populates="user",
    )
