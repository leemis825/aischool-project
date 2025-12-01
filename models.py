# models.py
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    JSON,
    BigInteger,
    Integer,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship

from database import Base


class MinwonSession(Base):
    __tablename__ = "minwon_session"

    session_id = Column(String(36), primary_key=True, index=True)
    received_at = Column(DateTime, nullable=False)
    text_raw = Column(Text, nullable=False)
    minwon_type = Column(String(20), nullable=False)
    risk_level = Column(String(10), nullable=False)
    handling_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)

    logs = relationship("EngineLog", back_populates="session")
    sms_infos = relationship("SmsInfo", back_populates="session")
    tickets = relationship("Ticket", back_populates="session")


class EngineLog(Base):
    __tablename__ = "engine_log"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("minwon_session.session_id"), nullable=False)
    stage = Column(String(20), nullable=False)
    request_text = Column(Text, nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)

    session = relationship("MinwonSession", back_populates="logs")


class SmsInfo(Base):
    __tablename__ = "sms_info"

    sms_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("minwon_session.session_id"), nullable=False)
    phone_number = Column(String(20), nullable=False)
    masked_phone = Column(String(20), nullable=False)
    agree_sms = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)

    session = relationship("MinwonSession", back_populates="sms_infos")


class Ticket(Base):
    __tablename__ = "ticket"

    ticket_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("minwon_session.session_id"), nullable=False)
    category = Column(String(50), nullable=False)
    risk_level = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False)
    dept_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    session = relationship("MinwonSession", back_populates="tickets")
