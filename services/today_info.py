# services/today_info.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date
from typing import Optional, Dict, Any, Tuple

import httpx
from pydantic import BaseModel

from core.config import (
    WEATHER_API_KEY,
    WEATHER_API_URL,       # current.json 또는 forecast.json, config에 정의된 그대로 사용
    KASI_SERVICE_KEY,
    KASI_LUNAR_URL,
    KASI_24DIV_URL,
)
from core.logging import logger


# ============================================================
# Pydantic 모델
# ============================================================

class WeatherInfo(BaseModel):
    location: str
    temp_c: Optional[float] = None
    condition_text: str = ""
    is_day: bool = True
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    feelslike_c: Optional[float] = None


class SeasonInfo(BaseModel):
    today: date
    lunar_date: Optional[str] = None   # 'YYYY-MM-DD' 형태
    solar_term: Optional[str] = None   # 입춘, 우수 같은 24절기 이름


class TodayInfo(BaseModel):
    weather: WeatherInfo
    season: SeasonInfo


# ============================================================
# 1) 날씨: WeatherAPI.com
# ============================================================

async def fetch_weather(location: str = "Gwangju") -> WeatherInfo:
    """
    WeatherAPI.com 의 forecast 기능을 사용해서
    - 현재 기온
    - 오늘 최저/최고 기온
    - 체감 온도
    를 가져온다.
    """
    if not WEATHER_API_KEY:
        raise RuntimeError("WEATHER_API_KEY 가 설정되지 않았습니다.")

    params = {
        "key": WEATHER_API_KEY,
        "q": location,
        "days": 1,      # 오늘 하루 예보
        "lang": "ko",
        "aqi": "no",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(WEATHER_API_URL, params=params)
        res.raise_for_status()
        data = res.json()

    # 안전하게 꺼내기
    location_name = data.get("location", {}).get("name", location)
    current = data.get("current", {}) or {}
    # forecast.json 인 경우 day 정보에서 최고/최저 확인
    forecast_day = (
        data.get("forecast", {})
        .get("forecastday", [{}])[0]
        .get("day", {})
    )

    return WeatherInfo(
        location=location_name,
        temp_c=current.get("temp_c"),
        condition_text=current.get("condition", {}).get("text", ""),
        is_day=bool(current.get("is_day", 1)),
        temp_min_c=forecast_day.get("mintemp_c"),
        temp_max_c=forecast_day.get("maxtemp_c"),
        feelslike_c=current.get("feelslike_c"),
    )


# ============================================================
# 2) 한국천문연구원(KASI) — 음력/절기
#    (예전에 잘 되던 코드 그대로 옮김)
# ============================================================

async def _fetch_lunar_date(target: date) -> Optional[str]:
    """
    양력 날짜(target)를 기준으로 음력 날짜(YYYY-MM-DD)를 조회해서 돌려준다.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY 가 설정되지 않았습니다.")

    params = {
        "solYear": target.strftime("%Y"),
        "solMonth": target.strftime("%m"),
        "solDay": target.strftime("%d"),
        "ServiceKey": KASI_SERVICE_KEY,
        "_type": "json",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(KASI_LUNAR_URL, params=params)
        res.raise_for_status()
        data = res.json()

    body = data.get("response", {}).get("body", {})
    if int(body.get("totalCount", 0)) == 0:
        return None

    item = body.get("items", {}).get("item")
    if not item:
        return None

    lun_year = int(item["lunYear"])
    lun_month = int(item["lunMonth"])
    lun_day = int(item["lunDay"])

    return f"{lun_year:04d}-{lun_month:02d}-{lun_day:02d}"


async def _fetch_seasonal_term(target: date) -> Optional[str]:
    """
    해당 날짜에 24절기가 있으면 그 이름(예: 입춘, 우수)을 반환.
    없으면 None.
    """
    if not KASI_SERVICE_KEY:
        raise RuntimeError("KASI_SERVICE_KEY 가 설정되지 않았습니다.")

    params = {
        "solYear": target.strftime("%Y"),
        "solMonth": target.strftime("%m"),
        "ServiceKey": KASI_SERVICE_KEY,
        "_type": "json",
        "numOfRows": "50",
        "pageNo": "1",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(KASI_24DIV_URL, params=params)
        res.raise_for_status()
        data = res.json()

    body = data.get("response", {}).get("body", {})
    if int(body.get("totalCount", 0)) == 0:
        return None

    items = body.get("items", {}).get("item")
    if not items:
        return None
    if isinstance(items, dict):
        items = [items]

    today_str = target.strftime("%Y%m%d")

    for item in items:
        if str(item.get("locdate")) == today_str:
            return str(item.get("dateName"))

    return None


async def fetch_season_info(target_date: Optional[date] = None) -> SeasonInfo:
    """
    오늘(또는 target_date)에 대한
    - 음력 날짜
    - 24절기 이름
    을 한 번에 묶어서 반환.
    """
    if target_date is None:
        target_date = date.today()

    if not KASI_SERVICE_KEY:
        logger.warning("KASI_SERVICE_KEY 가 없어 절기/음력은 비워 둡니다.")
        return SeasonInfo(today=target_date)

    lunar_date: Optional[str] = None
    solar_term: Optional[str] = None

    try:
        lunar_date = await _fetch_lunar_date(target_date)
    except Exception as e:
        logger.warning(f"Lunar API error: {e}")

    try:
        solar_term = await _fetch_seasonal_term(target_date)
    except Exception as e:
        logger.warning(f"Seasonal-term API error: {e}")

    return SeasonInfo(
        today=target_date,
        lunar_date=lunar_date,
        solar_term=solar_term,
    )


# ============================================================
# 3) 날씨 + 절기 묶어서 TodayInfo로 반환
# ============================================================

async def _gather_weather_and_season(location: str) -> Tuple[WeatherInfo, SeasonInfo]:
    """
    필요하면 나중에 asyncio.gather 로 병렬 호출도 가능.
    지금은 구조를 단순하게 하기 위해 순차 호출.
    """
    weather = await fetch_weather(location=location)
    season = await fetch_season_info()
    return weather, season


async def get_today_info(location: str = "Gwangju") -> TodayInfo:
    """
    /api/today-info 에서 직접 사용하는 헬퍼:
    날씨 + 절기를 한 번에 가져온다.
    """
    weather, season = await _gather_weather_and_season(location)
    return TodayInfo(weather=weather, season=season)
