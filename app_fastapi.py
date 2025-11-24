# app_fastapi.py
# -*- coding: utf-8 -*-

import uuid
import json
import os
import io
import urllib.request
import urllib.parse
import pymysql

from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import requests  # 🔹 네이버 TTS 호출용
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse  # 🔹 음성 스트리밍 응답
from pydantic import BaseModel, Field
from openai import OpenAI

from dotenv import load_dotenv
from speaker.stt_whisper import transcribe_bytes
from brain.minwon_engine import run_pipeline_once  # 민원 엔진

load_dotenv()  # .env 읽어오기

# ============================================================
# MySQL 연결 설정 (최소 수정 버전: pymysql)
# ============================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME", "complaint"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

def get_db_conn():
    return pymysql.connect(**DB_CONFIG)

@contextmanager
def db_cursor():
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def insert_chat_session_initial() -> int:
    """session 시작 시 빈 row 생성 후 id 반환"""
    sql = """
    INSERT INTO chat_session (
        stage, minwon_type, handling_type,
        summary, phone_suggestion, phone,
        confirm_question, location,
        risk_level, needs_visit,
        citizen_request, raw_keywords, memo_for_staff
    ) VALUES (
        NULL, NULL, NULL,
        NULL, NULL, NULL,
        NULL, NULL,
        NULL, NULL,
        NULL, NULL, NULL
    )
    """
    with db_cursor() as cur:
        cur.execute(sql)
        return cur.lastrowid


def insert_chat_message(session_id: int, sender: str, message: str) -> int:
    sql = """
    INSERT INTO chat_message (session_id, sender, message)
    VALUES (%s, %s, %s)
    """
    with db_cursor() as cur:
        cur.execute(sql, (session_id, sender, message))
        return cur.lastrowid


def update_chat_session_from_engine(
    session_id: int,
    engine_result: Dict[str, Any],
    original_text: str,
):


    user_facing = engine_result.get("user_facing") or {}
    staff_payload = engine_result.get("staff_payload") or {}

    # 값 변환 유틸
    def _to_scalar(v):
        if v is None:
            return None
        if isinstance(v, (str, int, float)):
            return v
        if isinstance(v, bool):
            return 1 if v else 0
        # list/dict/tuple 등은 JSON 문자열로 저장
        if isinstance(v, (list, dict, tuple)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)


    # needs_visit -> tinyint(1/0 or NULL)
    nv = staff_payload.get("needs_visit")
    if isinstance(nv, bool):
        needs_visit_val = 1 if nv else 0
    elif nv in (0, 1):
        needs_visit_val = nv
    else:
        needs_visit_val = None

    raw_keywords_val = staff_payload.get("raw_keywords")

    # 1) raw_keywords가 list이면 → 콤마로 join
    if isinstance(raw_keywords_val, list):
        raw_keywords_val = ",".join([str(x).strip() for x in raw_keywords_val if x])

    # 2) raw_keywords가 문자열이면 → strip
    elif isinstance(raw_keywords_val, str):
        raw_keywords_val = raw_keywords_val.strip()

    # 3) raw_keywords가 비어있으면 keywords를 fallback으로 사용
    else:
        kws = staff_payload.get("keywords")
        if isinstance(kws, list):
            raw_keywords_val = ",".join([str(x).strip() for x in kws if x])
        elif isinstance(kws, str):
            raw_keywords_val = kws.strip()
        else:
            raw_keywords_val = None

    sql = """
    UPDATE chat_session
    SET
        stage=%s,
        minwon_type=%s,
        handling_type=%s,
        summary=%s,
        phone_suggestion=%s,
        phone=%s,
        confirm_question=%s,
        location=%s,
        risk_level=%s,
        needs_visit=%s,
        citizen_request=%s,
        raw_keywords=%s,
        memo_for_staff=%s
    WHERE id=%s
    """

    params = (
        _to_scalar(engine_result.get("stage")),
        _to_scalar(engine_result.get("minwon_type")),
        _to_scalar(engine_result.get("handling_type")),

        _to_scalar(staff_payload.get("summary") or engine_result.get("summary")),
        _to_scalar(user_facing.get("phone_suggestion")),
        _to_scalar(user_facing.get("phone")),

        _to_scalar(user_facing.get("confirm_question")),
        _to_scalar(staff_payload.get("location") or engine_result.get("location")),

        _to_scalar(staff_payload.get("risk_level")),
        _to_scalar(needs_visit_val),

        _to_scalar(staff_payload.get("citizen_request") or original_text),
        _to_scalar(raw_keywords_val),
        _to_scalar(staff_payload.get("memo_for_staff")),

        session_id,
    )    

    with db_cursor() as cur:
        cur.execute(sql, params)

# 공통 유틸: 세션 보장
def ensure_session(session_id: Optional[str], source: str) -> str:
    """
    session_id가 없으면 새로 만들고,
    있으면 TEXT_SESSIONS에 세션이 있는지 보장한다.
    반환: 보장된 session_id
    """
    sid = session_id or str(uuid.uuid4())

    if sid not in TEXT_SESSIONS:
        db_session_id = insert_chat_session_initial()
        TEXT_SESSIONS[sid] = {
            "history": [],
            "pending_clarification": None,
            "db_session_id": db_session_id,
        }
        log_event(sid, {
            "type": "session_start",
            "source": source,
            "db_session_id": db_session_id,
        })

    return sid

AFFIRMATIVE_SHORTS = ["응", "네", "그래", "그래요", "맞아", "맞아요", "ㅇㅇ", "ㅇㅋ", "예", "웅"]
HESITATION_WORDS = ["음", "음...", "아", "아...", "흠", "저기", "그..."]
UNCLEAR_WORDS = ["그냥", "몰라", "모르겠어", "모르겠어요"]
REVERSE_QUESTION = ["맞지?", "맞죠?", "맞나?", "그렇지?"]
CALL_REQUEST = ["전화해줘", "전화해 주세요", "전화 부탁해", "전화 연결", "전화좀"]

def expand_short_affirmative(text: str, last_stage: Optional[str]) -> str:
    """
    사용자가 단답/머뭇거림/불명확/역질문/전화요청을 했을 때
    문장 확장하여 엔진이 이해할 수 있도록 보정.
    """
    t = text.strip()
    if t not in AFFIRMATIVE_SHORTS:
        return text  # 단답이 아니면 그대로 사용

    # 1) 기존 단답 처리
    if t in AFFIRMATIVE_SHORTS:
        # if last_stage == "clarification":
        #     return "네, 제가 말한 내용이 맞습니다. 계속 이어서 처리해 주세요."
        # elif last_stage == "guide":
        #     return "네, 안내해 주신 내용 이해했습니다."
        # elif last_stage == "handoff":
        #     return "네, 안내해 주신 절차대로 진행하겠습니다."
        # elif last_stage == "classification":
        #     return "네, 상황을 조금 더 설명드릴게요."
        # else:
            return "네, 계속 진행해 주세요."

    # 2) 머뭇거림 처리 (“음…”, “아…”)
    if t in HESITATION_WORDS:
        return "네, 계속 이어서 진행해 주세요."

    # 3) 불명확 발화 (“그냥”, “몰라”)
    if t in UNCLEAR_WORDS:
        return "제가 이해할 수 있도록 조금만 더 설명해 주세요."

    # 4) 역질문 (“맞지?”)
    if t in REVERSE_QUESTION:
        return "네, 제가 말한 내용이 맞습니다."

    # 5) 전화 요청 명령 (“전화해줘”)
    if t in CALL_REQUEST:
        return "전화 연결이 필요한 상황입니다. 안내해 주세요."
    
    return text  # 기본적으로 원문 반환


# 공통 유틸: 텍스트 턴 처리 + 영속화
def handle_turn_and_persist(
    session_id: str,
    original_text: str,          # 사용자가 말한 원문(ko든 외국어든)
    text_for_engine: str,        # 엔진에 넣을 텍스트(ko)
    source: str,
):
    # 🔹 직전 stage 가져오기
    session = TEXT_SESSIONS.get(session_id, {})
    history = session.get("history", [])
    last_engine_result = session.get("engine_result")  # ✅ 이전 결과 가져오기

    # ✅ 이전 stage 확인
    last_stage = last_engine_result.get("stage") if last_engine_result else None
    pending = session["pending_clarification"]
    db_session_id = session["db_session_id"]
    
    # 🔹 단답 확장
    expanded_text = expand_short_affirmative(original_text, last_stage)

    # ✅ **핵심: handoff 상태에서 긍정 단답이 들어오면 민원 접수 완료 처리**
    if last_stage == "handoff" and original_text.strip() in AFFIRMATIVE_SHORTS:
        # (1) 사용자 메시지 저장
        insert_chat_message(db_session_id, sender="senior", message=original_text)
        
        # (2) 민원 접수 완료 상태로 변경
        last_engine_result["stage"] = "completed"  # ✅ 새로운 stage
        last_engine_result["user_facing"]["main_message"] = "민원 접수가 완료되었습니다. 담당자가 확인 후 연락드리겠습니다."
        last_engine_result["user_facing"]["next_action_guide"] = ""
        last_engine_result["user_facing"]["phone_suggestion"] = ""
        last_engine_result["user_facing"]["confirm_question"] = ""
        
        # (3) 봇 응답 저장
        bot_text = last_engine_result["user_facing"]["main_message"]
        insert_chat_message(db_session_id, sender="bot", message=bot_text)
        
        # (4) DB 업데이트 (stage만 변경)
        update_chat_session_from_engine(
            db_session_id,
            engine_result=last_engine_result,
            original_text=original_text,
        )
        
        # (5) 세션 저장
        history.append({"role": "user", "content": original_text})
        session["engine_result"] = last_engine_result
        session["history"] = history
        TEXT_SESSIONS[session_id] = session
        
        # (6) 로그
        log_event(session_id, {
            "type": "completion",
            "source": source,
            "input_text": original_text,
            "final_stage": "completed",
            "db_session_id": db_session_id,
        })
        
        return last_engine_result, original_text  # ✅ 기존 결과 재사용

    # clarification 결합 규칙
    if pending is not None:
        prev_text = pending["original_text"]
        # 단답일 경우 엔진 입력에 포함시키지 않음
        if original_text.strip() in AFFIRMATIVE_SHORTS:
            used_text_for_engine = prev_text
        else:
            used_text_for_engine = f"{prev_text} 추가 위치 정보: {original_text}"

        used_text_for_user = f"{prev_text} 추가 위치 정보: {expanded_text}"
    else:
        # 단답이면 엔진 입력으로 보내지 않고 이전 문장을 재사용
        if original_text.strip() in AFFIRMATIVE_SHORTS and len(history) > 0:
            used_text_for_engine = history[-1]["content"]
        else:
            used_text_for_engine = original_text

        used_text_for_user = expanded_text

    # =======================================
    # 🔥 자연스러운 맥락 연결 (엔진이 이해할 수 있는 자연문 형태)
    # =======================================
    # 단답은 연결 금지 (의도 없음)
    if original_text.strip() not in AFFIRMATIVE_SHORTS:
        if len(history) > 0:
            prev_user_raw = history[-1]["content"]
            if prev_user_raw and prev_user_raw != original_text:
                # 자연어 맥락 결합
                used_text_for_engine = f"{prev_user_raw} 그리고 {original_text}"
        # else: 첫 발화는 그대로 사용
        else:
            used_text_for_engine = original_text


    # (1) 사용자 메시지 저장
    insert_chat_message(db_session_id, sender="senior", message=used_text_for_user)

    # (다국어라서 원문!=ko 번역이면 번역본도 저장)
    if used_text_for_engine != used_text_for_user:
        insert_chat_message(db_session_id, sender="senior_ko", message=used_text_for_engine)

    # (2) 엔진 실행
    engine_result = run_pipeline_once(used_text_for_engine, history)
    if not isinstance(engine_result, dict):
        engine_result = {}

    history.append({"role": "user", "content": used_text_for_engine})

    # clarification 상태 갱신
    if engine_result.get("stage") == "clarification":
        session["pending_clarification"] = {"original_text": used_text_for_engine}
    else:
        session["pending_clarification"] = None

    # (3) 봇 메시지 저장(현행 규칙 유지)
    bot_text = ""
    uf = engine_result.get("user_facing")
    if isinstance(uf, dict):
        bot_text = " ".join([str(v) for v in uf.values() if isinstance(v, str)])
    else:
        bot_text = str(uf) if uf else ""

    if bot_text:
        insert_chat_message(db_session_id, sender="bot", message=bot_text)

    # (4) 세션 snapshot 업데이트
    # citizen_request 등에 사용자 원문이 남아야 하므로 original_text=used_text_for_user
    update_chat_session_from_engine(
        db_session_id,
        engine_result=engine_result,
        original_text=used_text_for_user,
    )

    # 세션 스냅샷 저장
    session["engine_result"] = engine_result
    session["history"] = history
    TEXT_SESSIONS[session_id] = session

    # (5) 로그
    log_event(session_id, {
        "type": "turn",
        "source": source,
        "input_text": original_text,
        "engine_input_ko": used_text_for_engine,
        "engine_result": engine_result,
        "db_session_id": db_session_id,
    })

    return engine_result, used_text_for_engine




# ============================================================
# 경로 설정: 로그 디렉터리 (사후 분석용)
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_event(session_id: str, payload: Dict[str, Any]) -> None:
    """
    사후 분석용 JSONL 로그 기록.
    세션별로 1줄씩 쌓임.
    """
    ts = datetime.utcnow().isoformat()
    log_path = LOG_DIR / f"{session_id}.jsonl"

    record = {
        "timestamp": ts,
        "session_id": session_id,
        **payload,
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# 외부 API 키 / URL 설정
# ============================================================

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # WeatherAPI.com 키
KASI_SERVICE_KEY = os.getenv("KASI_SERVICE_KEY")  # 한국천문연구원(OpenAPI) 인증키 (Encoded 그대로)

WEATHER_API_URL = "http://api.weatherapi.com/v1/current.json"

KASI_LUNAR_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo"
)
KASI_24DIV_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/get24DivisionsInfo"
)

NAVER_API_KEY_ID = os.getenv("NAVER_API_KEY_ID")
NAVER_API_KEY = os.getenv("NAVER_API_KEY")

# 🔹 네이버 TTS API 엔드포인트 (test_tts.py에서 성공한 URL로 맞춰줄 것)
#NAVER_TTS_URL = "https://naveropenapi.apigw.ntruss.com/voice/v1/tts"
NAVER_TTS_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

# ============================================================
# OpenAI 클라이언트 (다국어 STT + 번역용)
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다. 다국어 STT/번역을 위해 API 키를 설정해 주세요.")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Whisper / 번역용 모델 (필요하면 .env에서 덮어쓰기)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "gpt-4o-mini-transcribe")
CHAT_MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")

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
  - 처리내용을 세션 별 DB에 저장
  을 수행합니다.
""",
    version="1.0.0",
)

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

TEXT_SESSIONS: Dict[str, Dict[str, Any]] = {}


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
    temp: float
    feels_like: float
    condition: str
    location: str


class LunarInfo(BaseModel):
    solar_date: str       # 양력 날짜 (YYYY-MM-DD)
    lunar_date: str       # 음력 날짜 (YYYY-MM-DD)
    seasonal_term: str    # 24절기 이름 (없으면 "")


class HeaderStatusResponse(BaseModel):
    now_iso: str          # ISO 포맷 현재 시각
    date_display: str     # 화면용 날짜 문자열 (예: '2025년 11월 12일 (수)')
    weather: Optional[WeatherInfo] = None
    lunar: Optional[LunarInfo] = None


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

    # 지금은 history 비우고 one-shot 으로만 처리
    history: List[Dict[str, str]] = []

    # 민원 엔진 실행
    engine_result = run_pipeline_once(raw_text, history=history)

    # 혹시 엔진에서 None 이나 이상한 값이 돌아올 경우 대비
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
    WeatherAPI.com 현재 날씨 조회.
    location 예: 'Gwangju', 'Seoul', '광주' 등
    """
    if not WEATHER_API_KEY:
        raise RuntimeError("WEATHER_API_KEY 환경변수가 설정되지 않았습니다.")

    params = {
        "key": WEATHER_API_KEY,
        "q": location,
        "lang": "ko",
        "aqi": "no",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(WEATHER_API_URL, params=params)
        res.raise_for_status()
        data = res.json()

    current = data["current"]
    cond = current["condition"]
    loc = data["location"]

    return WeatherInfo(
        temp=float(current["temp_c"]),
        feels_like=float(current["feelslike_c"]),
        condition=str(cond["text"]),
        location=str(loc["name"]),
    )


async def _fetch_lunar_date(today: date) -> str:
    """
    양력 today 기준 음력 날짜(YYYY-MM-DD)를 반환.
    한국천문연구원 LrsrCldInfoService/getLunCalInfo 사용.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY 환경변수가 설정되지 않았습니다.")

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
    오늘 날짜에 해당하는 24절기 이름을 반환.
    없으면 빈 문자열(""). 한국천문연구원 SpcdeInfoService/get24DivisionsInfo 사용.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY 환경변수가 설정되지 않았습니다.")

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
        print(f"[WARN] Lunar API error: {e}")

    try:
        seasonal_term = await _fetch_seasonal_term(today)
    except Exception as e:
        print(f"[WARN] Seasonal-term API error: {e}")

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
# 1. 텍스트 민원 세션 생성
# ============================================================

@app.post(
    "/api/session/start",
    summary="텍스트 민원 세션 생성",
    description="""
텍스트 기반 민원 세션을 하나 생성하고 `session_id`를 반환합니다.

### 사용 예시 (프론트)

1. 키오스크가 '민원을 말씀해 주세요' 화면으로 진입할 때
2. `/api/session/start`를 호출해 `session_id`를 하나 받는다.
3. 이후 모든 `/api/minwon/text-turn` 요청에 이 `session_id`를 포함한다.
""",
    tags=["session"],
)
def start_text_session():
    session_id = str(uuid.uuid4())

    # DB에 세션 row 생성
    db_session_id = insert_chat_session_initial()

    TEXT_SESSIONS[session_id] = {
        "history": [],
        "pending_clarification": None,
        "db_session_id": db_session_id,   # 🔹 추가
    }

    log_event(session_id, {"type": "session_start", "source": "api", "db_session_id": db_session_id})
    return {"session_id": session_id, "db_session_id": db_session_id}


# ============================================================
# 2. 텍스트 한 턴 처리 (clarification 결합 포함)
# ============================================================

@app.post(
    "/api/minwon/text-turn",
    response_model=TextTurnResponse,
    summary="텍스트 한 턴 처리 (민원 분류·안내)",
    description="""
한 번에 입력된 민원 텍스트(음성 STT 결과 등)를 분석해

- 민원 카테고리(도로/시설물/연금·복지/심리지원/생활민원/기타)
- 단순 안내 / 전화 연결 / 공식 민원 접수 필요 여부
- 주민 안내용 텍스트(user_facing)
- 담당자용 요약 정보(staff_payload)

를 포함한 JSON을 반환합니다.

### Clarification(추가 질문) 처리

- 직전 턴 결과의 `stage`가 `"clarification"`인 경우,
  - 이번에 들어온 `text`를 **이전 문장에 '추가 위치 정보: ...' 형태로 붙여서**
    하나의 문장으로 다시 분석합니다.
""",
    tags=["minwon"],
)
def process_text_turn(body: TextTurnRequest):
    # ✅ 세션 보장(기존 생성 로직 제거)
    session_id = ensure_session(body.session_id, source="text_turn")

    original_text = body.text.strip()
    if not original_text:
        raise HTTPException(status_code=400, detail="text가 비어 있습니다.")

    # ✅ 공통 턴 처리 + DB 저장
    engine_result, used_text = handle_turn_and_persist(
        session_id=session_id,
        original_text=original_text,
        text_for_engine=original_text,  # 텍스트는 그대로 ko 입력
        source="text_turn",
    )

    return TextTurnResponse(
        session_id=session_id,
        used_text=used_text,
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
    단일 JSONL 로그 파일(한 세션)을 읽어서
    - 최초/최종 timestamp
    - 이벤트 개수
    - 이벤트 타입 목록
    을 요약해서 반환.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[WARN] 로그 파일 읽기 실패: {path} ({e})")
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
    description="""
백엔드에서 기록한 JSONL 로그 파일을 기반으로

- 최근 세션 ID 목록
- 각 세션의 최초/최종 이벤트 시간
- 이벤트 개수
- 이벤트 타입 목록

을 요약해서 반환합니다.

발표용/모니터링용 뷰에서
'백엔드가 어떤 세션들을 처리했는지' 목록을 보여줄 때 사용합니다.
""",
    tags=["logs"],
)
def list_log_sessions(limit: int = 20):
    # 로그 디렉터리 내의 .jsonl 파일들을 최근 수정시간 기준으로 정렬
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
    description="""
주어진 `session_id`에 해당하는 JSONL 로그 파일을 읽어서

- 각 이벤트 레코드(타임스탬프, 타입, 입력 텍스트, 엔진 결과 등)를
  그대로 배열로 반환합니다.

프론트에서는 이 데이터를 기반으로
타임라인/테이블 형태로 '백엔드 내부 처리 흐름'을 시각화할 수 있습니다.
""",
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
    description="""
키오스크 대기 화면 상단에 표시할

- 현재 시간/날짜
- 날씨
- 음력 날짜
- 절기

정보를 반환합니다.

민원 대화와는 별개로, 대기 화면에서만 주기적으로 호출하면 됩니다.
""",
    tags=["status"],
)
async def get_header_status(location: str = "Gwangju"):
    now = datetime.now()
    date_display = now.strftime("%Y년 %m월 %d일 (%a)")

    weather: Optional[WeatherInfo] = None
    lunar: Optional[LunarInfo] = None

    try:
        weather = await fetch_weather(location)
    except Exception as e:
        print(f"[WARN] Weather API error: {e}")

    try:
        lunar = await get_lunar_and_seasonal(now.date())
    except Exception as e:
        print(f"[WARN] Lunar/Seasonal API error: {e}")

    return HeaderStatusResponse(
        now_iso=now.isoformat(),
        date_display=date_display,
        weather=weather,
        lunar=lunar,
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
        print("[WARN] stt_multilang_bytes에 빈 바이트가 전달되었습니다.")
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
        print(f"[WARN] Whisper multilang STT 호출 중 오류 발생: {e}")
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
        print(f"[WARN] 언어 감지 중 오류 발생: {e}")
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
        print(f"[WARN] 번역 중 오류 발생: {e}")
        return text


# ============================================================
# 4. 음성(STT) + 민원 엔진 한 번에 처리 (한국어 전용)
# ============================================================

@app.post(
    "/stt",
    summary="음성 파일(STT) + 민원 엔진 한 번에 처리 (한국어 전용)",
    description=(
        "프론트에서 녹음한 음성 파일(webm/mp3 등)을 업로드하면\n\n"
        "1. OpenAI Whisper를 사용해 STT (음성 → 텍스트, language='ko')\n"
        "2. 변환된 텍스트를 민원 엔진(run_pipeline_once)에 넣어 분류/요약\n\n"
        "까지 한 번에 처리하여 결과를 반환합니다."
    ),
    tags=["stt", "minwon"],
)
async def stt_and_minwon(request: Request):
    """
    - FormData로 올 때는 `audio` 또는 `file` 필드 이름을 사용한다고 가정
    - FastAPI의 UploadFile 파라미터(File(...))를 시그니처에서 빼고,
      request.form() 으로 직접 파싱해서 422 문제를 피한다.
    """

    # 1) multipart/form-data 파싱
    try:
        form = await request.form()
    except Exception as e:
        # 아예 multipart 자체가 아니거나, 파싱이 안 될 때
        raise HTTPException(
            status_code=400,
            detail=f"폼 데이터를 읽는 중 오류가 발생했습니다: {e}",
        )

    # 2) audio 또는 file 필드에서 업로드 파일 가져오기
    upload = form.get("audio") or form.get("file")

    if upload is None:
        # 파일 필드 자체가 없을 때
        raise HTTPException(
            status_code=400,
            detail="폼 데이터에 'audio' 또는 'file' 필드가 없습니다.",
        )

    # form.get(...) 결과가 UploadFile 이 아닌 경우 방어
    if not hasattr(upload, "filename") or not hasattr(upload, "read"):
        raise HTTPException(
            status_code=400,
            detail="업로드된 파일 형식을 인식할 수 없습니다.",
        )

    # 3) 실제 바이너리 읽기
    try:
        audio_bytes = await upload.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"업로드된 파일을 읽는 중 오류가 발생했습니다: {e}",
        )

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="비어 있는 오디오 파일입니다.")

    filename = upload.filename or "recording.webm"

    # 4) Whisper STT 호출 (한국어 고정)
    text = transcribe_bytes(
        audio_bytes,
        language="ko",
        file_name=filename,
    )

    # STT 실패
    if not text:
        return {
            "session_id": None,
            "text": "",
            "engine_result": None,
            "user_facing": None,
            "staff_payload": None,
        }

    # 5) session_id 옵션 받기 (FormData에서)
    session_id_from_form = form.get("session_id")
    session_id = ensure_session(session_id_from_form, source="stt")

    # ✅ 공통 턴 처리 + DB 저장
    engine_result, used_text = handle_turn_and_persist(
        session_id=session_id,
        original_text=text,      # 원문=ko
        text_for_engine=text,    # 엔진입력=ko
        source="stt",
    )

    return {
        "session_id": session_id,
        "db_session_id": TEXT_SESSIONS[session_id]["db_session_id"],
        "text": text,
        "used_text": used_text,
        "engine_result": engine_result,
        "user_facing": engine_result.get("user_facing", {}),
        "staff_payload": engine_result.get("staff_payload", {}),
    }


class TtsRequest(BaseModel):
    text: str  # 읽어 줄 문장


@app.post(
    "/tts",
    summary="네이버 CLOVA Voice TTS (텍스트 → 음성)",
    description=(
        "텍스트를 받아 네이버 CLOVA Voice API를 호출해 MP3 음성으로 변환합니다.\n"
        "프론트에서는 blob으로 받아 <audio> 태그로 재생하면 됩니다."
    ),
    tags=["tts"],
)
def tts(req: TtsRequest):
    if not NAVER_API_KEY_ID or not NAVER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="NAVER_API_KEY_ID 또는 NAVER_API_KEY 환경변수가 설정되지 않았습니다.",
        )

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 파라미터가 비어 있습니다.")

    # 🔹 test_tts.py와 동일한 방식으로 호출
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_API_KEY_ID,
        "X-NCP-APIGW-API-KEY": NAVER_API_KEY,
    }

    data = {
        "speaker": "nara",
        "speed": "0",
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
    description=(
        "프론트에서 녹음한 음성 파일(webm/mp3 등)을 업로드하면\n\n"
        "1. Whisper 다국어 STT (언어 자동 감지, 음성 → 원문 텍스트)\n"
        "2. 텍스트 언어 감지(ko/en/ja/…)\n"
        "3. 한국어로 번역해서 민원 엔진(run_pipeline_once)에 넣고 분류/요약\n"
        "4. 주민 안내 멘트(user_facing)를 다시 원래 언어로 번역해서 반환\n\n"
        "까지 한 번에 처리합니다."
    ),
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

    # ✅ session_id 옵션 받기 + 세션 보장
    session_id_from_form = form.get("session_id")
    session_id = ensure_session(session_id_from_form, source="stt_multilang")

    # ✅ 공통 턴 처리 + DB 저장(clarification 포함)
    engine_result, used_text = handle_turn_and_persist(
        session_id=session_id,
        original_text=original_text,       # 원문 저장
        text_for_engine=text_for_engine,   # ko 번역본 엔진 입력
        source="stt_multilang",
    )

    user_facing_ko = engine_result.get("user_facing") or {}
    staff_payload = engine_result.get("staff_payload") or {}

    # 5) 사용자에게 보여줄 언어 쪽 user_facing 생성 (기존 로직 유지)
    if lang == "ko":
        user_facing_for_user = user_facing_ko
    else:
        user_facing_for_user = {}
        for key, value in user_facing_ko.items():
            if isinstance(value, str) and value.strip():
                user_facing_for_user[key] = translate_text(value, target_lang=lang)
            else:
                user_facing_for_user[key] = value

    return {
        "session_id": session_id,
        "db_session_id": TEXT_SESSIONS[session_id]["db_session_id"],
        "original_lang": lang,
        "original_text": original_text,
        "engine_input_ko": used_text,
        "engine_result": engine_result,
        "user_facing_for_user": user_facing_for_user,
        "staff_payload": staff_payload,
    }



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
