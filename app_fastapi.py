# app_fastapi.py
# -*- coding: utf-8 -*-

import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field  # Field 추가

from brain.minwon_engine import run_pipeline_once  # 민원 엔진


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
# FastAPI 앱 기본 세팅 (Swagger 설명 포함)
# ============================================================

app = FastAPI(
    title="간편민원접수 백엔드 API (텍스트 전용 1단계)",
    description="""
마을 회관 키오스크용 **간편 민원 분류·안내 백엔드**의 텍스트 버전 API입니다.

- 키오스크(프론트)는 음성을 STT로 변환한 **텍스트**를 이 API로 전송합니다.
- 이 백엔드는 텍스트를 기반으로
  - 민원 카테고리 분류 (도로/시설물/연금·복지/심리지원/생활민원/기타)
  - 단순 안내/전화 연결/공식 민원 접수 여부 판단
  - 주민 안내 멘트(user_facing) 생성
  - 담당자용 요약(staff_payload) 생성
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
        None,
        description="이전 턴에서 받은 세션 ID. 첫 요청일 때는 비워두면 백엔드가 새로 생성합니다.",
        example=None,
    )
    text: str = Field(
        ...,
        description="민원 내용 텍스트 (음성 STT 결과 또는 키보드 입력)",
        example="우리집 앞에 나무가 쓰러져서 대문을 막았어",
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
        example="c3b9d2c8-1234-4f10-9f21-abcdef123456",
    )
    used_text: str = Field(
        ...,
        description="clarification(추가 위치 질문 등)까지 결합된 실제 분석 대상 텍스트",
        example="우리집 앞에 나무가 쓰러져서 대문을 막았어",
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
        example={
            "stage": "clarification",
            "minwon_type": "도로",
            "handling_type": "simple_guide",
            "need_call_transfer": False,
            "need_official_ticket": False,
            "user_facing": {
                "short_title": "추가 정보 확인",
                "main_message": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
                "next_action_guide": "예를 들어 ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요.",
                "phone_suggestion": "",
                "confirm_question": "",
            },
            "staff_payload": {
                "summary": "우리집 앞에 나무가 쓰러져서 대문을 막았어",
                "category": "도로",
                "location": "",
                "time_info": "",
                "risk_level": "긴급",
                "needs_visit": True,
                "citizen_request": "",
                "raw_keywords": ["우리집", "앞에", "나무가", "쓰러져서", "대문을"],
                "memo_for_staff": "위치 정보 부족으로 추가 질문 필요. 내용상 현장 출동이 필요해 보이는 민원일 수 있음.",
            },
        },
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
    return {"message": "간편민원접수 FastAPI (텍스트 전용) 동작 중"}


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
    TEXT_SESSIONS[session_id] = {
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
- 예:
  1. `우리집 앞에 나무가 쓰러져서 대문을 막았어` → stage=clarification
  2. `동곡리 마을회관 앞 골목이야` → 두 문장을 결합해 다시 분석 → 도로 + official_ticket
""",
    tags=["minwon"],
)
def process_text_turn(body: TextTurnRequest):
    # 1) 세션 준비
    session_id = body.session_id or str(uuid.uuid4())

    if session_id not in TEXT_SESSIONS:
        TEXT_SESSIONS[session_id] = {
            "history": [],
            "pending_clarification": None,
        }
        log_event(
            session_id,
            {"type": "session_start", "source": "implicit_by_text_turn"},
        )

    session = TEXT_SESSIONS[session_id]
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
