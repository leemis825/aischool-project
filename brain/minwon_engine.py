# -*- coding: utf-8 -*-
"""
민원 텍스트 엔진 — 최종 완성본
Clarification 1회만 / 추가 위치 정보 자동 인식 / 주소 처리 고도화
"""

import re
import json
from typing import Any, Dict, List, Tuple

from brain.utils_text import normalize, extract_keywords, is_critical, split_additional_location
from brain.rules_pension import build_pension_message
from .classifier import detect_minwon_type
from .summarizer import summarize_for_user, summarize_for_staff, build_fallback_summary
from .clarification_agent import decide_clarification_with_llm


# 민원 엔진이 구분해야 하는 Home-like 위치 표현
HOME_LIKE_PATTERN = (
    r"(우리집|집앞|집 앞|우리집 앞|집앞골목|집앞 골목|우리동네|우리 동네|동네|근처|이 근처|주변|인근)"
)

PLACEHOLDER_LOCATIONS = ("명시되지 않음", "미상", "알 수 없음")

DEFAULT_LOCATION = "동곡리 158번지 너와나 마을회관"


# -------------------------------------------------------------
# 1) 1차 규칙 기반 분류
# -------------------------------------------------------------
def rule_first_classify(text: str) -> Tuple[str, bool]:
    t = normalize(text)

    danger_keywords = ["쓰러졌", "불났", "폭발", "전선", "감전", "피가", "폭행", "위협", "죽고 싶"]
    if any(k in t for k in danger_keywords):
        return "도로", True

    detected = detect_minwon_type(t)
    needs_visit_map = {
        "도로": True,
        "시설물": True,
        "연금/복지": False,
        "심리지원": False,
        "생활민원": False,
    }
    c = detected or "기타"
    return c, needs_visit_map.get(c, False)


# -------------------------------------------------------------
# 2) Clarification 필요 여부(규칙 기반)
# -------------------------------------------------------------
def need_clarification(summary: Dict[str, Any], category: str, text: str, needs_visit_flag: bool) -> bool:
    """도로/시설물 + 방문 필요인데 위치가 모호하면 질문"""
    needs_visit = bool(summary.get("needs_visit") or needs_visit_flag)
    if not needs_visit:
        return False

    if category not in ("도로", "시설물"):
        return False

    t = normalize(text)
    t_no_space = t.replace(" ", "")

    # 이미 "추가 위치 정보" 포함 → 무조건 재질문 X
    if "추가위치정보" in t_no_space:
        return False

    raw_loc = (summary.get("location") or "").strip()
    if raw_loc in PLACEHOLDER_LOCATIONS:
        raw_loc = ""

    loc_norm = normalize(raw_loc) if raw_loc else ""

    has_home_like = bool(re.search(HOME_LIKE_PATTERN, t))
    has_loc_word = bool(
        re.search(
            r"(동\s|\d+동\b|리\s|\d+리\b|길|로|아파트|빌라|마을회관|시장|버스정류장|정류장|역|학교|병원|공원)",
            t,
        )
    )

    if (not raw_loc) and (not has_loc_word):
        return True

    if has_home_like and not has_loc_word:
        return True

    return False


# -------------------------------------------------------------
# 3) Clarification 응답 생성
# -------------------------------------------------------------
def build_clarification_response(text: str, category: str, needs_visit: bool, risk_level: str) -> Dict[str, Any]:
    uf = {
        "short_title": "추가 정보 확인",
        "main_message": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "next_action_guide": "예를 들어 ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요.",
        "phone_suggestion": "",
        "confirm_question": "지금 화면에 보이는 내용이 맞다면 '결과 확인' 버튼을 눌러 주세요.",
        "tts_listening": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "tts_summary": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "tts_result": "",
        "answer_core": "추가 위치 정보 확인이 필요합니다.",
    }

    sp = {
        "summary": text,
        "category": f"{category}-위치추가요청",
        "location": "",
        "time_info": "",
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": "정확한 위치 확인 후 현장 조치 필요",
        "raw_keywords": extract_keywords(text),
        "memo_for_staff": "위치 정보가 부족하여 추가 질문 단계.",
        "clarification_target": "location",
    }

    return {
        "stage": "clarification",
        "minwon_type": category,
        "handling_type": "official_ticket" if needs_visit else "simple_guide",
        "need_call_transfer": False,
        "need_official_ticket": needs_visit,
        "user_facing": uf,
        "staff_payload": sp,
    }


# -------------------------------------------------------------
# 4) 본 엔진 — run_pipeline_once
# -------------------------------------------------------------
def run_pipeline_once(text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    original = text.strip()
    if not original:
        return {
            "stage": "classification",
            "minwon_type": "기타",
            "handling_type": "simple_guide",
            "need_call_transfer": False,
            "need_official_ticket": False,
            "user_facing": {},
            "staff_payload": {},
        }

    category, needs_visit = rule_first_classify(original)

    handling = {
        "handling_type": "simple_guide",
        "need_call_transfer": False,
        "need_official_ticket": False,
        "risk_level": "보통",
        "needs_visit": needs_visit,
    }

    if category in ("도로", "시설물"):
        handling["handling_type"] = "official_ticket"
        handling["need_official_ticket"] = True
        handling["risk_level"] = "긴급" if is_critical(original) else "보통"
        handling["needs_visit"] = True

    elif category in ("연금/복지", "심리지원"):
        handling["need_call_transfer"] = True

    staff = summarize_for_staff(original, category, handling)

    analysis_text, additional_location = split_additional_location(original)
    already_history = bool(history)

    # -------------------------------------------------
    # 주소 기본값 주입 (도로/시설 제외)
    # -------------------------------------------------
    if not already_history and category not in ("도로", "시설물"):
        if not (staff.get("location") or "").strip():
            staff["location"] = DEFAULT_LOCATION

    # -------------------------------------------------
    # 추가 위치 정보 처리 (추가 위치 정보: ...)
    # -------------------------------------------------
    final_needs_visit = bool(staff.get("needs_visit") or needs_visit)
    risk = handling["risk_level"]

    if additional_location:
        extra_raw = additional_location.strip()
        extra_norm = normalize(extra_raw)
        extra_no_space = extra_norm.replace(" ", "")

        is_home_like = bool(re.search(HOME_LIKE_PATTERN, extra_norm))
        is_too_short = len(extra_no_space) <= 4
        ambiguous = is_home_like and is_too_short

        if final_needs_visit and not ambiguous:
            staff["location"] = extra_raw
        else:
            memo = staff.get("memo_for_staff") or ""
            add = f"주민이 말한 위치 표현: '{extra_raw}'"
            staff["memo_for_staff"] = memo + (" / " if memo else "") + add

    # -------------------------------------------------
    # Clarification 판단 (추가 위치 정보 턴이면 무조건 스킵)
    # -------------------------------------------------
    need_clar = False
    clar_reason = ""
    clar_target = "location"

    if not already_history:
        t_norm = normalize(analysis_text)
        t_no_space = t_norm.replace(" ", "")

        if "추가위치정보" not in t_no_space:
            rule_flag = need_clarification(staff, category, analysis_text, final_needs_visit)

            handling_info = {
                "handling_type": handling["handling_type"],
                "need_call_transfer": handling["need_call_transfer"],
                "need_official_ticket": handling["need_official_ticket"],
                "needs_visit": final_needs_visit,
                "risk_level": risk,
            }

            clar_llm = decide_clarification_with_llm(
                text=analysis_text,
                minwon_type=category,
                staff_payload=staff,
                handling_info=handling_info,
            )

            llm_flag = bool(clar_llm.get("needs_clarification", False))
            clar_reason = clar_llm.get("reason") or ""
            clar_target = clar_llm.get("target") or "location"

            need_clar = rule_flag or llm_flag

    if need_clar:
        resp = build_clarification_response(analysis_text, category, final_needs_visit, risk)
        memo = resp["staff_payload"].get("memo_for_staff") or ""
        if clar_reason:
            memo = memo + (" / " if memo else "") + f"LLM 판단 사유: {clar_reason}"
        resp["staff_payload"]["memo_for_staff"] = memo
        resp["staff_payload"]["clarification_target"] = clar_target
        return resp

    # -------------------------------------------------
    # 방문 필요한데 주소 여전히 없으면 fallback
    # -------------------------------------------------
    if final_needs_visit and not (staff.get("location") or "").strip():
        staff["location"] = DEFAULT_LOCATION

    # -------------------------------------------------
    # 최종 user-facing 구성
    # -------------------------------------------------
    empathy = "말씀해 주셔서 감사합니다. 많이 불편하셨겠습니다. "
    extra_pension = ""

    if category == "연금/복지":
        msg = build_pension_message(original)
        if msg:
            extra_pension = " " + msg

    if handling["handling_type"] == "simple_guide":
        next_step = summarize_for_user(original, category, handling)
        main_msg = f"{empathy}{category} 관련 안내로 처리됩니다.{extra_pension}"
    elif handling["handling_type"] == "contact_only":
        next_step = summarize_for_user(original, category, handling)
        main_msg = f"{empathy}{category} 관련 상담이 필요해 보입니다.{extra_pension}"
    else:
        next_step = "담당 부서에서 현장을 확인한 뒤, 필요한 조치를 진행할 예정입니다."
        main_msg = f"{empathy}{category} 관련 민원으로 접수하겠습니다."

    user_facing = {
        "short_title": f"{category} 관련 문의",
        "main_message": main_msg,
        "next_action_guide": next_step,
        "phone_suggestion": "" if handling["handling_type"] != "contact_only" else "",
        "confirm_question": "지금 화면에 보이는 내용이 맞으시면 '결과 확인' 버튼을 눌러 주세요.",
        "tts_listening": main_msg + " " + next_step,
        "tts_summary": main_msg,
        "tts_result": next_step,
        "answer_core": f"{category} 관련 문의 요약 안내입니다.",
    }

    staff_payload = {
        "summary": staff.get("summary") or build_fallback_summary(original, category),
        "category": staff.get("category", category),
        "location": staff.get("location", ""),
        "time_info": staff.get("time_info", ""),
        "risk_level": staff.get("risk_level", risk),
        "needs_visit": staff.get("needs_visit", final_needs_visit),
        "citizen_request": staff.get("citizen_request", ""),
        "raw_keywords": staff.get("raw_keywords", []),
        "memo_for_staff": staff.get("memo_for_staff", ""),
    }

    stage = "guide" if not handling["need_official_ticket"] else "handoff"

    return {
        "stage": stage,
        "minwon_type": category,
        "handling_type": handling["handling_type"],
        "need_call_transfer": handling["need_call_transfer"],
        "need_official_ticket": handling["need_official_ticket"],
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }
# -------------------------------------------------
# 기존 코드 호환용 헬퍼 (옛 코드에서 사용)
# -------------------------------------------------
from typing import Dict as _Dict, Any as _Any, List as _List

def decide_stage_and_text(text: str, history: _List[_Dict[str, str]]) -> _Dict[str, _Any]:
    """
    기존 코드에서 사용하던 헬퍼 함수.
    내부적으로 run_pipeline_once를 그대로 호출한다.
    """
    return run_pipeline_once(text, history)
