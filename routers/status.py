# routers/status.py
from fastapi import APIRouter
from datetime import datetime
from typing import Optional

from core.logging import logger
from core.config import WEATHER_API_KEY
from app_fastapi import fetch_weather, get_lunar_and_seasonal, HeaderStatusResponse

router = APIRouter()

@router.get(
    "/api/status/header",
    response_model=HeaderStatusResponse,
    summary="대기 화면용 헤더 정보",
    tags=["status"],
)
async def get_header_status(location: str = "Gwangju"):
    now = datetime.now()
    date_display = now.strftime("%Y년 %m월 %d일 (%a)")

    weather = None
    lunar = None

    try:
        weather = await fetch_weather(location)
    except Exception as e:
        logger.warning(f"Weather API error: {e}")

    try:
        lunar = await get_lunar_and_seasonal(now.date())
    except Exception as e:
        logger.warning(f"Lunar/Seasonal API error: {e}")

    return HeaderStatusResponse(
        now_iso=now.isoformat(),
        date_display=date_display,
        weather=weather,
        lunar=lunar,
    )
