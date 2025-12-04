from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.base import Base


class ComplaintMessage(Base):
    __tablename__ = "complaint_messages"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(BigInteger, ForeignKey("complaints.id"), nullable=False)

    # 누가 말했는지
    role = Column(String(20), nullable=False)  # 'user', 'bot', 'admin'

    # ✅ 실제 텍스트 내용 (시민/봇/관리자 모두 여기에 저장)
    content = Column(Text, nullable=True)

    # 선택: 음성 파일 경로들
    audio_url = Column(String(255), nullable=True)     # 시민 원본 음성 파일
    tts_audio_url = Column(String(255), nullable=True) # 봇/관리자 TTS 파일

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    complaint = relationship(
        "Complaint",
        back_populates="messages",
    )
