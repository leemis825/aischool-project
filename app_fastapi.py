# app_fastapi.py
# -*- coding: utf-8 -*-

from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, MinwonSession
from fastapi import Depends
from datetime import datetime
import uuid

import os
print("🔥 Loaded app_fastapi from:", os.path.abspath(__file__))

import json
import os
import io
import urllib.request
import urllib.parse

from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import requests  # 🔹 네이버 TTS 호출용
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse  # 🔹 음성 스트리밍 응답
from pydantic import BaseModel, Field
from openai import OpenAI

from dotenv import load_dotenv
from speaker.stt_whisper import transcribe_bytes
from brain import minwon_engine
from brain.text_session_state import TextSessionState
from brain.turn_router import choose_issue_for_followup
from brain.minwon_engine import run_pipeline_once, decide_stage_and_text, save_engine_log

# 🔹 STT 멀티턴(TextSessionState)용 세션 딕셔너리
TEXT_SESSIONS: Dict[str, TextSessionState] = {}

# 🔹 텍스트-only /api/minwon/text-turn용 세션 딕셔너리
TEXT_TURN_SESSIONS: Dict[str, Dict[str, Any]] = {}

# 🔹 환경 설정 / 로깅은 core 모듈에서 가져옵니다.
from core.config import (
    LOG_DIR,
    WEATHER_API_KEY,
    KASI_SERVICE_KEY,
    WEATHER_API_URL,
    KASI_LUNAR_URL,
    KASI_24DIV_URL,
    NAVER_API_KEY_ID,
    NAVER_API_KEY,
    NAVER_TTS_URL,
    OPENAI_API_KEY,
    WHISPER_MODEL,
    CHAT_MODEL,
)
from core.logging import logger, log_event

# ============================================================
# OpenAI 클라이언트 (다국어 STT + 번역용)
# ============================================================

if not OPENAI_API_KEY:
    raise RuntimeError(
        ".env에 OPENAI_API_KEY가 없습니다. 다국어 STT/번역을 위해 API 키를 설정해 주세요."
    )

openai_client = OpenAI(api_key=OPENAI_API_KEY)

#------------------------ STT 멀티턴 세션관리 ----------------------
def get_state(session_id: str) -> TextSessionState:
    """
    /stt/multi 전용 세션 상태 관리.
    A/B/C 이슈 스레드, clarification 결합 등은 TextSessionState에 위임.
    """
    if session_id not in TEXT_SESSIONS:
        TEXT_SESSIONS[session_id] = TextSessionState()
        log_event(session_id, {"type": "session_start", "source": "stt_or_text"})
    return TEXT_SESSIONS[session_id]

# ============================================================
# FastAPI 앱 기본 세팅 (Swagger 설명 포함)
# ============================================================

app = FastAPI(
    title="간편민원접수 백엔드 API",
    description="""
마을 회관 키오스크용 **간편 민원 분류·안내 백엔드** API입니다.

- 키오스크(프론트)는 음성을 STT로 변환한 **텍스트** 또는 음성 파일을 이 API로 전송합니다.
- 이 백엔드는 텍스트를 기반으로
  - 민원 카테고리 분류 (도로/시설물/연금·복지/심리지원/생활민원/기타)
  - 단순 안내/전화 연결/공식 민원 접수 여부 판단
  - 주민 안내 멘트(user_facing) 생성
  - 담당자용 요약(staff_payload) 생성
  을 수행합니다.
""",
    version="1.0.0",
)

print("🔥 DEBUG: app_fastapi.py loaded. registered routes:")
for r in app.routes:
    print("  -", r.path)

@app.get(
    "/debug/routes",
    tags=["debug"],
    summary="현재 FastAPI에 등록된 라우트 목록 디버그용",
)
def debug_routes():
    return [r.path for r in app.routes]

# ============================================================
# 테이블 자동 생성이 필요하면 한 번만 실행 (이미 만들었으면 생략 가능)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 🔹 민원세션 저장/갱신 도우미 ---------------------------------
def create_or_update_minwon_session(
    db: Session,
    session_id: str,
    used_text: str,
    engine_result: Dict[str, Any],
):
    """
    - 한 세션(session_id)당 1행 유지
    - 이미 있으면 내용만 갱신, 없으면 새로 INSERT
    """
    if not engine_result:
        return

    minwon_type = engine_result.get("minwon_type") or "기타"
    handling_type = engine_result.get("handling_type") or "simple_guide"

    staff_payload = engine_result.get("staff_payload") or {}
    risk_level = staff_payload.get("risk_level") or "보통"

    need_official = bool(engine_result.get("need_official_ticket"))
    need_call = bool(engine_result.get("need_call_transfer"))

    if need_official:
        status = "ticket_required"
    elif need_call:
        status = "call_recommended"
    else:
        status = "guide_only"

    obj = (
        db.query(MinwonSession)
        .filter(MinwonSession.session_id == session_id)
        .first()
    )

    if obj is None:
        # 🔸 최초 생성
        obj = MinwonSession(
            session_id=session_id,
            received_at=datetime.utcnow(),
            text_raw=used_text,
            minwon_type=minwon_type,
            risk_level=risk_level,
            handling_type=handling_type,
            status=status,
        )
        db.add(obj)
    else:
        # 🔸 같은 세션에 대해 내용이 바뀔 때 갱신
        obj.text_raw = used_text
        obj.minwon_type = minwon_type
        obj.risk_level = risk_level
        obj.handling_type = handling_type
        obj.status = status

    db.commit()
    db.refresh(obj)
    return obj
# ============================================================
# STT 요청 공통 처리 유틸 (폼 파싱 + session_id 추출)
# ============================================================

async def _parse_stt_request(request: Request) -> Dict[str, Any]:
    """
    /stt 관련 엔드포인트에서 공통으로 사용하는
    - multipart/form-data 파싱
    - session_id 추출(폼/헤더/쿼리)
    - 오디오 바이트/파일명 추출
    로직을 한 곳에 모은 함수입니다.
    """
    try:
        form = await request.form()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"폼 파싱 오류: {e}")

    # session_id 는 있으면 쓰고, 없으면 새로 생성
    session_id_raw = (
        form.get("session_id")
        or request.headers.get("X-Session-ID")
        or request.query_params.get("session_id")
    )
    session_id = (session_id_raw or "").strip() or str(uuid.uuid4())

    # 오디오 파일 추출 (audio 또는 file 필드)
    upload = form.get("audio") or form.get("file")
    if upload is None:
        raise HTTPException(status_code=400, detail="오디오 파일이 없습니다.")

    try:
        audio_bytes = await upload.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"오디오 읽기 오류: {e}")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="비어 있는 오디오입니다.")

    filename = getattr(upload, "filename", None) or "record.webm"

    return {
        "session_id": session_id,
        "audio_bytes": audio_bytes,
        "filename": filename,
        "form": form,
    }

# CORS: 개발 단계에서는 * 허용, 배포 시에는 도메인 제한 권장
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 텍스트 모드용 세션 상태 (메모리)
# ============================================================

class TextTurnRequest(BaseModel):
    """
    텍스트 한 턴 입력용 요청 바디 모델.
    - session_id: 기존 대화 세션 ID (없으면 새로 생성됨)
    - text: STT 결과나 키보드 입력 등, 한 번에 처리할 민원 문장
    """
    session_id: Optional[str] = Field(
        default=None,
        description="이전 턴에서 받은 세션 ID. 첫 요청일 때는 비워두면 백엔드가 새로 생성합니다.",
        examples=[None],
    )

    text: str = Field(
        ...,
        description="민원 내용 텍스트",
        examples=["우리집 앞에 나무가 쓰러져서 대문을 막았어"],
    )


class TextTurnResponse(BaseModel):
    """
    텍스트 한 턴 처리 결과 응답 모델.
    - session_id: 이 턴이 속한 세션 ID
    - used_text: 실제 엔진에 들어간 텍스트 (clarification 결합 포함)
    - engine_result: 민원 엔진 공통 스키마(JSON)
    """
    session_id: str = Field(
        ...,
        description="현재 대화 세션 ID. 이후 요청에서도 이 값을 그대로 사용하면 됩니다.",
        examples=["c3b9d2c8-1234-4f10-9f21-abcdef123456"],
    )
    used_text: str = Field(
        ...,
        description="clarification(추가 위치 질문 등)까지 결합된 실제 분석 대상 텍스트",
        examples=["우리집 앞에 나무가 쓰러져서 대문을 막았어"],
    )
    engine_result: Dict[str, Any] = Field(
        ...,
        description=(
            "민원 엔진 결과 JSON.\n"
            "- stage: classification | guide | handoff | clarification\n"
            "- minwon_type: 도로/시설물/연금/복지/심리지원/생활민원/기타\n"
            "- handling_type: simple_guide | contact_only | official_ticket\n"
            "- user_facing: 주민 안내용 텍스트 묶음\n"
            "- staff_payload: 담당자용 요약 정보"
        ),
    )

# ============================================================
# 날씨 / 음력 / 절기 모델
# ============================================================

class WeatherInfo(BaseModel):
    temp: int          # 현재 기온
    max_temp: int      # 최고 기온
    min_temp: int      # 최저 기온
    condition: str     # 날씨 상태 (맑음, 흐림 등)
    location: str      # 지역 이름
    feels_like: int    # 체감 온도 (WeatherAPI feelslike_c 사용)

class LunarInfo(BaseModel):
    solar_date: str       # 양력 날짜 (YYYY-MM-DD)
    lunar_date: str       # 음력 날짜 (YYYY-MM-DD)
    seasonal_term: str    # 24절기 이름 (없으면 "")

class HeaderStatusResponse(BaseModel):
    now_iso: str          # ISO 포맷 현재 시각
    date_display: str     # 화면용 날짜 문자열 (예: '2025년 11월 12일 (수)')
    weather: Optional[WeatherInfo] = None
    lunar: Optional[LunarInfo] = None
    holiday: str = ""     # 공휴일 이름 (없으면 빈 문자열)

# ============================================================
# 텍스트 기반 민원 분석 단일 호출 API
# ============================================================

class MinwonAnalyzeRequest(BaseModel):
    text: str


@app.post(
    "/api/minwon/analyze",
    summary="텍스트 기반 민원 분석 (STT 없이)",
    tags=["minwon"],
)
async def analyze_minwon(req: MinwonAnalyzeRequest):
    """
    - 프론트/외부 시스템에서 이미 텍스트로 받은 민원을
      우리 민원 엔진(run_pipeline_once)으로 분류/요약해서 반환하는 API
    - STT는 포함하지 않고, text -> engine_result 만 담당
    """

    raw_text = (req.text or "").strip()
    if not raw_text:
        return {
            "input_text": "",
            "engine_result": None,
            "user_facing": None,
            "staff_payload": None,
        }

    history: List[Dict[str, str]] = []

    engine_result = run_pipeline_once(raw_text, history=history)

    if not isinstance(engine_result, dict):
        engine_result = {}

    user_facing = engine_result.get("user_facing") or {}
    staff_payload = engine_result.get("staff_payload") or {}

    return {
        "input_text": raw_text,
        "engine_result": engine_result,
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }

# ============================================================
# 대기 화면용 보조 함수들 (실제 외부 API 연동)
# ============================================================

async def fetch_weather(location: str = "Gwangju") -> WeatherInfo:
    """
    WeatherAPI.com의 Forecast 기능을 사용하여
    현재 기온과 오늘 최저/최고/체감 기온을 가져옵니다.
    """
    print("DEBUG WEATHER API KEY inside fetch_weather:", WEATHER_API_KEY)
    print("[DEBUG] WEATHER location param:", location)
    if not WEATHER_API_KEY:
        logger.error("❌ [WeatherAPI] API 키가 없습니다. .env 파일을 확인하세요.")
        raise RuntimeError("WEATHER_API_KEY가 설정되지 않았습니다.")

    url = "http://api.weatherapi.com/v1/forecast.json"

    params = {
        "key": WEATHER_API_KEY,
        "q": location,
        "days": 1,       # 오늘 하루 예보
        "lang": "ko",
        "aqi": "no",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, params=params)
            print("[DEBUG] WEATHER status:", res.status_code)
            print("[DEBUG] WEATHER body:", res.text[:200])
            if res.status_code != 200:
                logger.error(f"❌ [WeatherAPI] 호출 실패: {res.status_code} - {res.text}")
                res.raise_for_status()

            data = res.json()

        current = data["current"]
        today_forecast = data["forecast"]["forecastday"][0]["day"]

        logger.info(f"✅ [WeatherAPI] 날씨 조회 성공: {location}")

        return WeatherInfo(
            temp=round(current["temp_c"]),
            max_temp=round(today_forecast["maxtemp_c"]),
            min_temp=round(today_forecast["mintemp_c"]),
            condition=current["condition"]["text"],
            location=data["location"]["name"],
            feels_like=round(current.get("feelslike_c", current["temp_c"])),
        )

    except Exception as e:
        logger.warning(f"⚠️ [WeatherAPI] 처리 중 에러 발생: {e}")
        raise e

async def _fetch_lunar_date(today: date) -> str:
    """
    양력 today 기준 음력 날짜(YYYY-MM-DD)를 반환.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY가 설정되지 않았습니다.")

    params = {
        "solYear": today.strftime("%Y"),
        "solMonth": today.strftime("%m"),
        "solDay": today.strftime("%d"),
        "ServiceKey": KASI_SERVICE_KEY,
        "_type": "json",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(KASI_LUNAR_URL, params=params)
        res.raise_for_status()
        data = res.json()

    body = data["response"]["body"]
    if int(body.get("totalCount", 0)) == 0:
        return ""

    item = body["items"]["item"]  # 하루 데이터 1개라고 가정
    lun_year = int(item["lunYear"])
    lun_month = int(item["lunMonth"])
    lun_day = int(item["lunDay"])

    return f"{lun_year:04d}-{lun_month:02d}-{lun_day:02d}"


async def _fetch_seasonal_term(today: date) -> str:
    """
    오늘 날짜에 해당하는 24절기 이름을 반환. 없으면 빈 문자열.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY가 설정되지 않았습니다.")

    params = {
        "solYear": today.strftime("%Y"),
        "solMonth": today.strftime("%m"),
        "ServiceKey": KASI_SERVICE_KEY,
        "_type": "json",
        "numOfRows": "50",
        "pageNo": "1",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(KASI_24DIV_URL, params=params)
        res.raise_for_status()
        data = res.json()

    body = data["response"]["body"]
    if int(body.get("totalCount", 0)) == 0:
        return ""

    items = body["items"]["item"]
    if isinstance(items, dict):
        items = [items]

    today_str = today.strftime("%Y%m%d")
    for item in items:
        if str(item["locdate"]) == today_str:
            return str(item["dateName"])

    return ""


async def get_lunar_and_seasonal(today: Optional[date] = None) -> LunarInfo:
    """
    오늘 기준 음력 날짜 + 절기 이름을 한 번에 반환.
    """
    if today is None:
        today = date.today()

    lunar_date = ""
    seasonal_term = ""

    try:
        lunar_date = await _fetch_lunar_date(today)
    except Exception as e:
        logger.warning(f"Lunar API error: {e}")

    try:
        seasonal_term = await _fetch_seasonal_term(today)
    except Exception as e:
        logger.warning(f"Seasonal-term API error: {e}")

    return LunarInfo(
        solar_date=today.isoformat(),
        lunar_date=lunar_date,
        seasonal_term=seasonal_term,
    )

# ============================================================
# 0. 헬스 체크 / 기본 라우트
# ============================================================

@app.get(
    "/",
    summary="헬스 체크",
    description="백엔드 서버가 정상 동작 중인지 확인하는 간단한 엔드포인트입니다.",
    tags=["health"],
)
def root():
    return {"message": "간편민원접수 FastAPI 동작 중"}

# ============================================================
# 1. 텍스트 민원 세션 생성 (텍스트-only)
# ============================================================

@app.post(
    "/api/session/start",
    summary="텍스트 민원 세션 생성",
    tags=["session"],
)
def start_text_session():
    session_id = str(uuid.uuid4())
    TEXT_TURN_SESSIONS[session_id] = {
        "history": [],
        "pending_clarification": None,
    }

    log_event(session_id, {"type": "session_start", "source": "api"})

    return {"session_id": session_id}

# ============================================================
# 2. 텍스트 한 턴 처리 (clarification 결합 포함)
# ============================================================

@app.post(
    "/api/minwon/text-turn",
    response_model=TextTurnResponse,
    summary="텍스트 한 턴 처리 (민원 분류·안내)",
    tags=["minwon"],
)
def process_text_turn(
    body: TextTurnRequest,
    db: Session = Depends(get_db),
):
    """
     텍스트 한 턴을 민원 엔진에 넘기고,
    세션 상태 + DB(minwon_session, engine_log)에 반영한다.
    """
    # 1) 세션 준비
    session_id = body.session_id or str(uuid.uuid4())

    if session_id not in TEXT_TURN_SESSIONS:
        TEXT_TURN_SESSIONS[session_id] = {
            "history": [],
            "pending_clarification": None,
        }
        log_event(
            session_id,
            {"type": "session_start", "source": "implicit_by_text_turn"},
        )

    session = TEXT_TURN_SESSIONS[session_id]
    history: List[Dict[str, str]] = session["history"]
    pending = session["pending_clarification"]

    original_text = body.text.strip()

    # 2) clarification 결합 처리
    if pending is not None:
        prev_text = pending["original_text"]
        use_text = f"{prev_text} 추가 위치 정보: {original_text}"
    else:
        use_text = original_text

    # 3) 민원 엔진 호출
    engine_result = run_pipeline_once(use_text, history)
    
    # 3-1) 🔹 DB에 민원세션 upsert
    create_or_update_minwon_session(
        db=db,
        session_id=session_id,
        used_text=use_text,
        engine_result=engine_result,
    )

    # 3-2) 🔹 엔진 로그 저장 (테이블: engine_log)
    try:
        save_engine_log(
            db=db,
            session_id=session_id,
            stage=engine_result.get("stage", "unknown"),
            request_text=use_text,
            response=engine_result,
        )
    except Exception as e:
        # DB 로그 실패해도 전체 흐름은 깨지지 않도록
        logger.warning(f"EngineLog 저장 중 오류 발생: {e}")
        
    # 4) history 업데이트
    history.append({"role": "user", "content": use_text})

    # 5) clarification 상태 업데이트
    if engine_result.get("stage") == "clarification":
        session["pending_clarification"] = {"original_text": use_text}
    else:
        session["pending_clarification"] = None

    # 6) 로그 기록 (사후 분석용)
    log_event(
        session_id,
        {
            "type": "text_turn",
            "input_text": original_text,
            "used_text": use_text,
            "engine_result": engine_result,
        },
    )

    # 7) 응답
    return TextTurnResponse(
        session_id=session_id,
        used_text=use_text,
        engine_result=engine_result,
    )

# ============================================================
# 로그 조회용 모델 & 유틸
# ============================================================

class LogSessionSummary(BaseModel):
    session_id: str
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    event_count: int
    event_types: List[str]


class LogSessionListResponse(BaseModel):
    sessions: List[LogSessionSummary]


class LogSessionDetailResponse(BaseModel):
    session_id: str
    events: List[Dict[str, Any]]


def _summarize_log_file(path: Path) -> Optional[LogSessionSummary]:
    """
    단일 JSONL 로그 파일(한 세션)을 읽어서 요약 정보 생성.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.warning(f"로그 파일 읽기 실패: {path} ({e})")
        return None

    if not lines:
        return None

    event_count = len(lines)
    event_types: List[str] = []
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None

    for idx, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except Exception:
            continue

        ts = rec.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        etype = rec.get("type")
        if etype and etype not in event_types:
            event_types.append(etype)

    session_id = path.stem  # 파일명에서 .jsonl 제거

    return LogSessionSummary(
        session_id=session_id,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        event_count=event_count,
        event_types=event_types,
    )

# ============================================================
#  로그 세션 목록 조회
# ============================================================

@app.get(
    "/api/logs/sessions",
    response_model=LogSessionListResponse,
    summary="로그 세션 목록 조회",
    tags=["logs"],
)
def list_log_sessions(limit: int = 20):
    files = sorted(
        LOG_DIR.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    summaries: List[LogSessionSummary] = []
    for path in files[:limit]:
        summary = _summarize_log_file(path)
        if summary is not None:
            summaries.append(summary)

    return LogSessionListResponse(sessions=summaries)

# ============================================================
#  특정 세션 로그 상세 조회
# ============================================================

@app.get(
    "/api/logs/{session_id}",
    response_model=LogSessionDetailResponse,
    summary="특정 세션 로그 상세 조회",
    tags=["logs"],
)
def get_log_session_detail(session_id: str, max_events: int = 200):
    log_path = LOG_DIR / f"{session_id}.jsonl"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="해당 session_id의 로그가 없습니다.")

    events: List[Dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx >= max_events:
                    break
                try:
                    rec = json.loads(line)
                    events.append(rec)
                except Exception:
                    continue
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"로그 파일을 읽는 중 오류가 발생했습니다: {e}",
        )

    return LogSessionDetailResponse(
        session_id=session_id,
        events=events,
    )

# ============================================================
# 3. 대기 화면용 헤더 정보 API
# ============================================================

@app.get(
    "/api/status/header",
    response_model=HeaderStatusResponse,
    summary="대기 화면용 헤더 정보(시간/날짜/날씨/음력/절기)",
    tags=["status"],
)
async def get_header_status(
    location: str = "Gwangju",
    test_date: Optional[str] = None,
):
    """
    - location: 날씨 조회용 위치 (기본 Gwangju)
    - test_date: '2025-11-30' 같이 넣으면 해당 날짜 기준으로
      date_display / 음력 / 절기를 계산 (개발·테스트용)
    """
    now = datetime.now()

    if test_date:
        try:
            # 'YYYY-MM-DD' 형식만 지원
            fake_date = datetime.fromisoformat(test_date)
            now = fake_date
        except ValueError:
            logger.warning(f"[header_status] invalid test_date: {test_date}")

    date_display = now.strftime("%Y년 %m월 %d일 (%a)")

    weather: Optional[WeatherInfo] = None
    lunar: Optional[LunarInfo] = None
    holiday_name: str = ""

    try:
        weather = await fetch_weather(location)
    except Exception as e:
        logger.warning(f"Weather API error: {e}")

    try:
        lunar = await get_lunar_and_seasonal(now.date())
    except Exception as e:
        logger.warning(f"Lunar/Seasonal API error: {e}")

    # TODO: 필요하면 여기에서 공휴일 API 연동해서 holiday_name 채우기
    # 지금은 기본적으로 빈 문자열 반환
    return HeaderStatusResponse(
        now_iso=now.isoformat(),
        date_display=date_display,
        weather=weather,
        lunar=lunar,
        holiday=holiday_name,
    )

# ============================================================
# 다국어 STT + 언어 감지 + 번역 유틸 함수
# ============================================================

def stt_multilang_bytes(audio_bytes: bytes, file_name: str = "recording.webm") -> str:
    """
    Whisper에 language 파라미터를 주지 않고 호출해서
    언어 자동 감지 + 텍스트 변환을 수행한다.
    """
    if not audio_bytes:
        logger.warning("[WARN] stt_multilang_bytes에 빈 바이트가 전달되었습니다.")
        return ""

    bio = io.BytesIO(audio_bytes)
    if file_name:
        try:
            bio.name = file_name  # type: ignore[attr-defined]
        except Exception:
            pass

    try:
        resp = openai_client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=bio,
            response_format="text",  # 순수 텍스트
        )
        if isinstance(resp, str):
            return resp.strip()
        text = getattr(resp, "text", "") or str(resp)
        return text.strip()
    except Exception as e:
        logger.warning(f"Whisper multilang STT 호출 중 오류 발생: {e}")
        return ""


def detect_language(text: str) -> str:
    """
    입력 텍스트의 언어를 ISO 639-1 코드(ko, en, ja, zh 등)로 감지.
    """
    if not text:
        return "ko"

    try:
        resp = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "사용자 문장의 언어를 감지하고, "
                        "ISO 639-1 두 글자 코드만 소문자로 출력하세요. "
                        "예: ko, en, ja, zh."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=8,
        )
        code = resp.choices[0].message.content.strip().lower()
        code = code.replace("`", "").replace(" ", "")

        for cand in ["ko", "en", "ja", "zh", "vi"]:
            if cand in code:
                return cand

        return (code[:2] or "ko")
    except Exception as e:
        logger.warning(f"언어 감지 중 오류 발생: {e}")
        return "ko"


def translate_text(text: str, target_lang: str) -> str:
    """
    text를 target_lang 언어로 번역.
    target_lang 예: 'ko', 'en', 'ja' ...
    """
    if not text:
        return ""

    try:
        resp = openai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"다음 문장을 {target_lang} 언어로 자연스럽게 번역해 주세요. "
                        "추가 설명 없이 번역된 문장만 출력하세요."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"번역 중 오류 발생: {e}")
        return text

# ============================================================
# 4-A. 음성(STT) + 민원 엔진 — 싱글턴 모드
#       - 세션 상태 / 멀티턴 관리 없음
#       - 한 번 STT → 한 번 run_pipeline_once 로 끝나는 단일 호출
# ============================================================

@app.post(
    "/stt/single",
    summary="음성 기반 민원 처리 (싱글턴, 세션 상태 저장 안 함)",
    tags=["stt"],
)
async def stt_and_minwon_single(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("=== 🟦 STT(single) 요청 도착 ===")

    parsed = await _parse_stt_request(request)
    session_id = parsed["session_id"]
    audio_bytes = parsed["audio_bytes"]
    filename = parsed["filename"]

    # 1) Whisper STT
    text = transcribe_bytes(audio_bytes, language="ko", file_name=filename)
    original = (text or "").strip()
    logger.info(f"[STT(single) 결과] {original}")

    if not original:
        return {
            "session_id": session_id,
            "text": "",
            "used_text": "",
            "engine_result": None,
            "user_facing": {},
            "staff_payload": {},
        }

    # 2) 싱글턴이므로 history/clarification 합치기 없이 그대로 엔진에 넣음
    engine_result = run_pipeline_once(original, history=[])
    
    # 2-1) 🔹 민원세션 DB upsert
    create_or_update_minwon_session(
        db=db,
        session_id=session_id,
        used_text=original,
        engine_result=engine_result,
    )

    # 2-2) 🔹 엔진 로그 DB 저장
    try:
        save_engine_log(
            db=db,
            session_id=session_id,
            stage=engine_result.get("stage", "unknown"),
            request_text=original,
            response=engine_result,
        )
    except Exception as e:
        logger.warning(f"EngineLog 저장 중 오류 발생: {e}")
        
    # 3) 로그 기록
    log_event(
        session_id,
        {
            "type": "stt_single_turn",
            "input_text": original,
            "used_text": original,
            "engine_result": engine_result,
        },
    )

    logger.info("=== 🟩 STT(single) 응답 완료 ===")

    return {
        "session_id": session_id,
        "text": original,            # 원문 = 사용 텍스트
        "used_text": original,
        "engine_result": engine_result,
        "user_facing": engine_result.get("user_facing", {}),
        "staff_payload": engine_result.get("staff_payload", {}),
    }

# ============================================================
# 4-B. 음성(STT) + 민원 엔진 — 멀티턴 모드
#       - TextSessionState 사용
#       - clarification / 이슈 A,B,C 스레드 관리
# ============================================================

@app.post(
    "/stt/multi",
    summary="음성 기반 민원 처리 (멀티턴, 세션/이슈 상태 관리)",
    tags=["stt"],
)
async def stt_and_minwon_multi(
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("=== 🟦 STT(multi) 요청 도착 ===")

    parsed = await _parse_stt_request(request)
    session_id = parsed["session_id"]
    audio_bytes = parsed["audio_bytes"]
    filename = parsed["filename"]

    logger.info(f"[session_id] {session_id}")

    # 🔹 멀티턴용 세션 상태 가져오기 (A/B 스레드 포함)
    state = get_state(session_id)

    # 1) Whisper STT
    text = transcribe_bytes(audio_bytes, language="ko", file_name=filename)
    original = (text or "").strip()
    logger.info(f"[STT(multi) 결과] {original}")

    if not original:
        return {
            "session_id": session_id,
            "issue_id": None,
            "text": "",
            "used_text": "",
            "engine_result": None,
            "user_facing": {},
            "staff_payload": {},
        }

    # 2) 🔥 멀티턴(clarification) + A/B 스레드 결합
    effective_text = state.build_effective_text(original)

    # 3) 엔진 실행
    engine_result = run_pipeline_once(effective_text, [])
    
    # 3-1) 🔹 민원세션 DB upsert
    create_or_update_minwon_session(
        db=db,
        session_id=session_id,
        used_text=effective_text,
        engine_result=engine_result,
    )

    # 3-2) 🔹 엔진 로그 DB 저장
    try:
        save_engine_log(
            db=db,
            session_id=session_id,
            stage=engine_result.get("stage", "unknown"),
            request_text=effective_text,
            response=engine_result,
        )
    except Exception as e:
        logger.warning(f"EngineLog 저장 중 오류 발생: {e}")
        
    # 4) 🔥 A/B/C 이슈 라우팅
    turn = state.register_turn(
        user_raw=original,
        effective_text=effective_text,
        engine_result=engine_result,
    )
    issue_id = turn.issue_id  # ← A/B/C 구분됨

    # 5) 로그 기록
    log_event(
        session_id,
        {
            "type": "stt_turn",
            "issue_id": issue_id,
            "input_text": original,
            "used_text": effective_text,
            "engine_result": engine_result,
        },
    )

    logger.info("=== 🟩 STT(multi) 응답 완료 ===")

    return {
        "session_id": session_id,
        "issue_id": issue_id,
        "text": original,
        "used_text": effective_text,
        "engine_result": engine_result,
        "user_facing": engine_result.get("user_facing", {}),
        "staff_payload": engine_result.get("staff_payload", {}),
    }

# ============================================================
# 4-C. 레거시 /stt 엔드포인트
#       - 현재는 멀티턴(/stt/multi)와 동일하게 동작
#       - 프론트에서 점진적으로 /stt/single 또는 /stt/multi 로 옮겨가면 됨
# ============================================================

@app.post(
    "/stt",
    summary="(레거시) 음성 기반 민원 처리 — 현재는 멀티턴과 동일",
    tags=["stt"],
)
async def stt_and_minwon(request: Request):
    return await stt_and_minwon_multi(request)

# ============================================================
# TTS 요청 모델 & 엔드포인트
# ============================================================

class TtsRequest(BaseModel):
    """
    네이버 클라우드 CLOVA Voice TTS 요청 모델.
    - text   : 읽어 줄 문장 (필수)
    - speaker: 목소리 이름 (기본값 'nara')
    - speed  : 말하기 속도 (-5 ~ 5, 기본 -2: 조금 느리게)
    """
    text: str = Field(..., description="읽어 줄 문장")
    speaker: str = Field(
        default="nara",
        description="CLOVA Voice speaker 이름 (예: nara, jinho 등)",
    )
    speed: int = Field(
        default=-2,
        ge=-5,
        le=5,
        description="말하기 속도 (-5=매우 느림, 0=보통, 5=매우 빠름)",
    )


@app.post(
    "/tts",
    summary="네이버 CLOVA Voice TTS (텍스트 → 음성)",
    tags=["tts"],
)
def tts(req: TtsRequest):
    """
    텍스트를 네이버 CLOVA TTS로 변환하여 MP3 스트리밍으로 반환합니다.

    프론트 예시:
    - 기본(조금 느리게):
      { "text": "안녕하세요.", "speed": -2 }

    - 더 천천히:
      { "text": "안녕하세요.", "speed": -4 }

    - speaker 변경:
      { "text": "안녕하세요.", "speaker": "jinho", "speed": -1 }
    """
    if not NAVER_API_KEY_ID or not NAVER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="NAVER_API_KEY_ID 또는 NAVER_API_KEY 환경변수가 설정되지 않았습니다.",
        )

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 파라미터가 비어 있습니다.")

    # speaker / speed 정리
    speaker = (req.speaker or "nara").strip() or "nara"

    # pydantic에서 이미 -5~5 범위 체크를 하지만, 혹시 몰라 한 번 더 방어적 클램핑
    speed_int = req.speed
    if speed_int < -5:
        speed_int = -5
    if speed_int > 5:
        speed_int = 5

    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_API_KEY_ID,
        "X-NCP-APIGW-API-KEY": NAVER_API_KEY,
    }

    data = {
        "speaker": speaker,
        "speed": str(speed_int),
        "text": text,
    }

    try:
        res = requests.post(NAVER_TTS_URL, headers=headers, data=data, timeout=10)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"TTS 요청 중 네트워크 오류: {e}",
        )

    if res.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"TTS API 응답 오류: {res.status_code}, {res.text}",
        )

    return StreamingResponse(io.BytesIO(res.content), media_type="audio/mpeg")

# ============================================================
# 5. 다국어 음성(STT) + 민원 엔진 한 번에 처리
# ============================================================

@app.post(
    "/stt/multilang",
    summary="다국어 음성(STT) + 민원 엔진 처리 (원어 응답 포함)",
    tags=["stt", "minwon"],
)
async def stt_and_minwon_multilang(request: Request):
    # 1) multipart/form-data 파싱
    try:
        form = await request.form()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"폼 데이터를 읽는 중 오류가 발생했습니다: {e}",
        )

    upload = form.get("audio") or form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(
            status_code=400,
            detail="폼 데이터에 'audio' 또는 'file' 필드가 없거나 잘못되었습니다.",
        )

    try:
        audio_bytes = await upload.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"업로드된 파일을 읽는 중 오류가 발생했습니다: {e}",
        )

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="비어 있는 오디오 파일입니다.")

    filename = getattr(upload, "filename", None) or "recording.webm"

    # 2) 다국어 Whisper STT
    original_text = stt_multilang_bytes(audio_bytes, file_name=filename)

    if not original_text:
        return {
            "session_id": None,
            "original_lang": None,
            "original_text": "",
            "engine_input_ko": "",
            "engine_result": None,
            "user_facing_for_user": None,
            "staff_payload": None,
        }

    # 3) 언어 감지
    lang = detect_language(original_text)

    # 4) 한국어로 변환해 민원 엔진에 넣을 텍스트 준비
    if lang == "ko":
        text_for_engine = original_text
    else:
        text_for_engine = translate_text(original_text, target_lang="ko")

    history: List[Dict[str, str]] = []
    engine_result = run_pipeline_once(text_for_engine, history)
    if not isinstance(engine_result, dict):
        engine_result = {}

    user_facing_ko = engine_result.get("user_facing") or {}
    staff_payload = engine_result.get("staff_payload") or {}

    # 5) 사용자에게 보여줄 언어 쪽 user_facing 생성
    if lang == "ko":
        user_facing_for_user = user_facing_ko
    else:
        user_facing_for_user = {}
        for key, value in user_facing_ko.items():
            if isinstance(value, str) and value.strip():
                user_facing_for_user[key] = translate_text(value, target_lang=lang)
            else:
                user_facing_for_user[key] = value

    # 6) 세션/로그 기록
    session_id = str(uuid.uuid4())
    log_event(
        session_id,
        {
            "type": "stt_multilang_turn",
            "original_lang": lang,
            "original_text": original_text,
            "engine_input_ko": text_for_engine,
            "engine_result": engine_result,
            "source": "stt_multilang_endpoint",
        },
    )

    return {
        "session_id": session_id,
        "original_lang": lang,
        "original_text": original_text,
        "engine_input_ko": text_for_engine,
        "engine_result": engine_result,
        "user_facing_for_user": user_facing_for_user,
        "staff_payload": staff_payload,
    }
    
# ============================================================
# 6. DB 연결 테스트용 엔드포인트
# ============================================================

@app.post("/db-test")
def db_test(db: Session = Depends(get_db)):
    """
    DB 연결 테스트용: 가짜 세션 1개 삽입 후 다시 조회해서 돌려줌
    """
    session_id = str(uuid.uuid4())

    new_session = MinwonSession(
        session_id=session_id,
        received_at=datetime.utcnow(),
        text_raw="테스트 민원입니다.",
        minwon_type="테스트",
        risk_level="보통",
        handling_type="simple_guide",
        status="test",
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {
        "inserted_session_id": new_session.session_id,
        "received_at": new_session.received_at.isoformat(),
    }


# ============================================================
# 디버그용: 최종 라우트 목록 출력
# ============================================================
print("🔥 FINAL ROUTES:")
for r in app.routes:
    print("  -", r.path)

# ============================================================
# uvicorn 실행용 엔트리포인트
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
