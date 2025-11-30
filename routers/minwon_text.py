# routers/minwon_text.py
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any

from brain.minwon_engine import run_pipeline_once
from core.logging import log_event
from app_fastapi import TEXT_SESSIONS, TextTurnRequest, TextTurnResponse

router = APIRouter()

@router.post(
    "/api/minwon/text-turn",
    response_model=TextTurnResponse,
    summary="텍스트 한 턴 처리",
    tags=["minwon"],
)
def process_text_turn(body: TextTurnRequest):
    session_id = body.session_id or "new"

    session_id = body.session_id or str(uuid.uuid4())
    if session_id not in TEXT_SESSIONS:
        TEXT_SESSIONS[session_id] = {
            "history": [],
            "pending_clarification": None,
        }

    session = TEXT_SESSIONS[session_id]
    history: List[Dict[str, str]] = session["history"]
    pending = session["pending_clarification"]

    original_text = body.text.strip()
    use_text = f"{pending['original_text']} 추가 위치 정보: {original_text}" if pending else original_text

    engine_result = run_pipeline_once(use_text, history)
    history.append({"role": "user", "content": use_text})

    if engine_result.get("stage") == "clarification":
        session["pending_clarification"] = {"original_text": use_text}
    else:
        session["pending_clarification"] = None

    log_event(
        session_id,
        {
            "type": "text_turn",
            "input_text": original_text,
            "used_text": use_text,
            "engine_result": engine_result,
        },
    )

    return TextTurnResponse(
        session_id=session_id,
        used_text=use_text,
        engine_result=engine_result,
    )
