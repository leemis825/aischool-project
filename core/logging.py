# core/logging.py
# -*- coding: utf-8 -*-

import sys
import json
import logging
from datetime import datetime
from typing import Any, Dict

from .config import LOG_DIR

# ------------------------------------------------
# 터미널 출력용 logger
# ------------------------------------------------
logger = logging.getLogger("minwon_kiosk")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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
