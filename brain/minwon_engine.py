# -*- coding: utf-8 -*-
"""
민원 텍스트 엔진 — 최종 완성본
"""

import re
from typing import Any, Dict, List, Tuple

from brain.utils_text import (
    normalize,
    extract_keywords,
    is_critical,
    split_additional_location,
)
from brain.rules_pension import build_pension_message
from .classifier import detect_minwon_type
from .summarizer import summarize_for_user, summarize_for_staff, build_fallback_summary
from .clarification_agent import decide_clarification_with_llm

# ------------------------------
# 기본 패턴 / 기본 위치
# ------------------------------
HOME_LIKE_PATTERN = (
    r"(우리집|집앞|집 앞|우리집 앞|집앞골목|집앞 골목|우리동네|우리 동네|동네|근처|이 근처|주변|인근)"
)

PLACEHOLDER_LOCATIONS = ("명시되지 않음", "미상", "알 수 없음")

DEFAULT_LOCATION = "동곡리 158번지 너와나 마을회관"

# =============================================================================
# 1) 규칙 기반 1차 분류
# =============================================================================
def rule_first_classify(text: str) -> Tuple[str, bool]:
    t = normalize(text)

    # 위험 키워드 → 무조건 현장 방문
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


# =============================================================================
# 2) Clarification 필요 여부 판단(규칙 기반)
# =============================================================================
def need_clarification(summary: Dict[str, Any], category: str, text: str, needs_visit_flag: bool) -> bool:
    needs_visit = bool(summary.get("needs_visit") or needs_visit_flag)
    if not needs_visit:
        return False

    if category not in ("도로", "시설물"):
        return False

    t = normalize(text)
    t_no_space = t.replace(" ", "")

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


# =============================================================================
# 3) Clarification 응답 생성
# =============================================================================
def build_clarification_response(text: str, category: str, needs_visit: bool, risk_level: str) -> Dict[str, Any]:
    uf = {
        "short_title": "추가 정보 확인",
        "main_message": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "next_action_guide": "예를 들어 ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요.",
        "phone_suggestion": "",
        "confirm_question": "",
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


# =============================================================================
# 4) 위치 텍스트 정제(clean)
# =============================================================================
def clean_location_for_user(raw: str) -> str:
    if not raw:
        return ""

    txt = raw.strip()

    # 첫 문장만 추출(?,! 등 기준)
    for sep in ["\n", "!", "?"]:
        if sep in txt:
            parts = [p.strip() for p in txt.split(sep) if p.strip()]
            if parts:
                txt = parts[-1]
                break

    txt = re.sub(r"^(아|어|그|저기|거기)\s*[,\s]+", "", txt)
    # '입니다', '이에요' 등 + 그 뒤에 조사 1~2글자까지 제거
    txt = re.sub(r"(입니다|이에요|에요|예요|이요)([^\w\s])?", "", txt).strip()
    txt = re.sub(r"(입니다|이에요|에요|예요|이요)(에|에서|으로|로|를|을)?", "", txt).strip()

    txt = txt.rstrip(".,").strip()
    txt = re.sub(r"\s+", " ", txt)

    return txt


# =============================================================================
# 5) 본 엔진
# =============================================================================
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

    # -------------------------------------------------
    # 1) 분류 + handling 기본값
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 2) 담당자용 요약 생성
    # -------------------------------------------------
    staff = summarize_for_staff(original, category, handling)

    analysis_text, additional_location = split_additional_location(original)
    already_history = bool(history)

    # -------------------------------------------------
    # 3) 1턴 시설물/도로 + 위치 없음 → 무조건 Clarification
    # -------------------------------------------------
    if (
        not already_history
        and category in ("도로", "시설물")
        and not additional_location
        and not (staff.get("location") or "").strip()
    ):
        t_norm = normalize(original)
        has_loc_word = bool(
            re.search(
                r"(동\s|\d+동\b|리\s|\d+리\b|길|로|아파트|빌라|마을회관|시장|버스정류장|정류장|역|학교|병원|공원)",
                t_norm,
            )
        )
        if not has_loc_word:
            final_needs_visit = True
            risk = "긴급" if is_critical(original) else "보통"
            return build_clarification_response(original, category, final_needs_visit, risk)

    # -------------------------------------------------
    # 4) 추가 위치 정보 반영
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
    # 5) Clarification 판단 (⚠️ 들여쓰기 & 조건 완전 수정됨)
    # -------------------------------------------------
    need_clar = False
    clar_reason = ""
    clar_target = "location"

    if not already_history:
        orig_norm = normalize(original)
        orig_no_space = orig_norm.replace(" ", "")

        is_additional_loc_turn = (
            "추가위치정보" in orig_no_space 
            or (additional_location and additional_location.strip() != "")
        )

        has_confident_location = bool(staff.get("location"))

        if (not is_additional_loc_turn) and (not has_confident_location):
            rule_flag = need_clarification(
                staff, category, analysis_text, final_needs_visit
            )

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
        resp = build_clarification_response(original, category, final_needs_visit, risk)
        memo = resp["staff_payload"].get("memo_for_staff") or ""
        if clar_reason:
            memo += (" / " if memo else "") + f"LLM 판단 사유: {clar_reason}"
        resp["staff_payload"]["memo_for_staff"] = memo
        resp["staff_payload"]["clarification_target"] = clar_target
        return resp

    # -------------------------------------------------
    # 6) 위치 기본값 보정
    # -------------------------------------------------
    if final_needs_visit and not (staff.get("location") or "").strip():
        staff["location"] = DEFAULT_LOCATION

    # -------------------------------------------------
    # 7) Summary / Result 텍스트 생성
    # -------------------------------------------------
    raw_location = staff.get("location", "")
    cleaned_location = clean_location_for_user(raw_location)

    if cleaned_location:
        summary_text = f"{cleaned_location} {category} 고장"
    else:
        summary_text = f"{category} 관련 민원"

    if cleaned_location:
        summary_tts = (
            f"말씀해 주신 내용은 {cleaned_location}에 있는 {category} 문제가 맞으실까요? "
        )
    else:
        summary_tts = (
            f"말씀해 주신 내용은 {category} 관련 민원이 맞으실까요? "
        )

    empathy = "말씀해 주셔서 감사합니다. 많이 불편하셨겠습니다. "

    if handling["handling_type"] == "official_ticket":
        result_text = "담당 부서에서 현장을 확인해 조치할 예정입니다."

        if cleaned_location:
            result_tts = (
                f"{empathy}{cleaned_location}에 있는 {category} 문제는 "
                "담당 부서에서 현장을 확인해 조치할 예정입니다. "
                "확인 후 화면 아무 곳이나 눌러 주세요."
            )
        else:
            result_tts = (
                f"{empathy}{category} 관련 민원은 "
                "담당 부서에서 내용을 확인해 조치할 예정입니다. "
                "확인 후 화면 아무 곳이나 눌러 주세요."
            )
    else:
        guide_text = summarize_for_user(original, category, handling)
        result_text = guide_text
        result_tts = (
            f"{empathy}{guide_text} "
            "확인 후 화면 아무 곳이나 눌러 주세요."
        )

    # -------------------------------------------------
    # 8) user_facing / staff_payload 구성
    # -------------------------------------------------
    user_facing = {
        "short_title": f"{category} 관련 문의",
        "summary_text": summary_text,
        "summary_tts": summary_tts,
        "result_text": result_text,
        "result_tts": result_tts,
        "main_message": empathy + f"{category} 관련 민원으로 접수하겠습니다.",
        "next_action_guide": result_text,
        "phone_suggestion": "",
        "confirm_question": "요약 내용이 맞으시면 예 버튼을 눌러 주세요.",
        "tts_listening": summary_tts,
        "tts_summary": summary_tts,
        "tts_result": result_tts,
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


# =============================================================================
# 6) 기존 코드 호환용
# =============================================================================
def decide_stage_and_text(text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    return run_pipeline_once(text, history)
