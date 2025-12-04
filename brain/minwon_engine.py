# -*- coding: utf-8 -*-
"""
민원 텍스트 엔진 — 1단계(텍스트 전용) 최종본

리턴 스키마:
{
  "stage": "classification" | "guide" | "handoff" | "clarification",
  "minwon_type": "도로" | "시설물" | "연금/복지" | "심리지원" | "생활민원" | "기타",
  "handling_type": "simple_guide" | "contact_only" | "official_ticket",
  "need_call_transfer": bool,
  "need_official_ticket": bool,
  "user_facing": {
    "short_title": str,
    "main_message": str,
    "next_action_guide": str,
    "phone_suggestion": str,
    "confirm_question": str,
    "tts_listening": str,  # ListeningPage에서 읽어줄 스크립트
    "tts_summary": str,    # SummaryPage에서 읽어줄 스크립트
    "tts_result": str,     # ResultPage에서 읽어줄 스크립트
    "answer_core": str     # SummaryPage에서 크게 보여줄 핵심 한 줄 요약(질문 요약)
  },
  "staff_payload": {
    "summary": str,
    "category": str,
    "location": str,
    "time_info": str,
    "risk_level": "긴급" | "보통" | "경미",
    "needs_visit": bool,
    "citizen_request": str,
    "raw_keywords": list[str],
    "memo_for_staff": str
  }
}
"""

import re
import json
from typing import Any, Dict, List, Tuple, Optional
from sqlalchemy.orm import Session

from .classifier import detect_minwon_type
from .summarizer import summarize_for_user, summarize_for_staff, build_fallback_summary

from models import EngineLog
from datetime import datetime

# -------------------- 엔진 로그 저장 --------------------
def save_engine_log(db: Session, session_id: str, stage: str, request_text: str, response: dict):
    log = EngineLog(
        session_id=session_id,
        stage=stage,
        request_text=request_text,
        response_json=response,
        created_at=datetime.utcnow(),
    )
    db.add(log)
    db.commit()

# 멀티턴용 확인/부정 단어
CONFIRM_WORDS = ["네", "예", "맞아요", "맞습니다", "응", "그래요", "그렇습니다"]
DENY_WORDS = ["아니요", "아뇨", "틀렸어요", "다른데요", "그건 아닌데"]


def decide_stage_and_text(user_text: str, session_state: dict) -> dict:
    """
    (현재는 상위 레이어에서 사용 가능하도록 남겨둔 함수)
    멀티턴/싱글턴 전환 + stage 결정 로직의 기본 뼈대.
    """
    last = session_state.get("last_engine_result")

    # 1) 첫 발화: 이전 결과 없음 → 요약 확인부터
    if not last:
        return {
            "stage": "clarification",
            "llm_needed": True,
            "reuse_last_result": False,
            "mode": "first_turn",
        }

    # 2) 직전이 clarification 단계였던 경우
    if last.get("stage") == "clarification":
        text_stripped = user_text.strip()

        # 2-1. "네/맞아요" 계열 → 최종 안내 단계
        if any(w in text_stripped for w in CONFIRM_WORDS):
            return {
                "stage": "guide",
                "llm_needed": True,
                "reuse_last_result": True,
                "mode": "confirm_summary",
            }

        # 2-2. "아니요/틀렸어요" 계열 → 다시 분류
        if any(w in text_stripped for w in DENY_WORDS):
            return {
                "stage": "classification",
                "llm_needed": True,
                "reuse_last_result": False,
                "mode": "reclassify",
            }

        # 2-3. 그 외: 사용자가 내용을 수정해서 다시 말한 것으로 보고 재분류
        return {
            "stage": "classification",
            "llm_needed": True,
            "reuse_last_result": False,
            "mode": "reclassify_with_new_text",
        }

    # 3) 그 외에는 기본적으로 guide/handoff 단계에서 단일턴 종료
    return {
        "stage": "guide",
        "llm_needed": False,
        "reuse_last_result": True,
        "mode": "noop",
    }


# ============================================================
#  규칙/LLM 결합 엔진 — 단일 턴용 (run_pipeline_once)
# ============================================================

from .utils_text import (
    normalize,
    is_critical,
    extract_keywords,
    split_additional_location,
)
HOME_LIKE_PATTERN = r"(우리집|집앞|집 앞|우리집 앞|집앞골목|집앞 골목|우리동네|우리 동네|동네|근처|이 근처|주변|인근)"
from .rules_pension import compute_pension_age, build_pension_message
from .llm_client import call_chat, MODEL, TEMP_GLOBAL, TEMP_CLASSIFIER


def rule_first_classify(text: str) -> Tuple[str, bool]:
    """
    간단한 키워드 기반 1차 분류.
    (민원 유형, needs_visit 후보) 를 리턴.
    """
    t = normalize(text)

    # 위험/안전 키워드가 있으면 우선 도로/시설 쪽으로 치우치도록 설계 가능
    danger_keywords = ["쓰러졌", "불났", "폭발", "전선", "감전", "피가", "폭행", "위협", "죽고 싶"]
    if any(k in t for k in danger_keywords):
        # 기본적으로 '도로' 로 태깅하고, LLM에서 보정하도록 둔다.
        return "도로", True

    # 간단 도로/시설/연금/심리지원/생활민원/기타 매핑
    detected_type = detect_minwon_type(t)

    # 1차 기본 needs_visit 설정
    needs_visit_map = {
        "도로": True,
        "시설물": True,
        "연금/복지": False,
        "심리지원": False,
        "생활민원": False,
    }
    primary = detected_type or "기타"
    return primary, needs_visit_map.get(primary, False)


def need_clarification(
    summary_data: Dict[str, Any],
    category: str,
    text: str,
    needs_visit_flag: bool,
) -> bool:
    """
    출동이 필요한 민원에서 '위치가 모호하거나 아예 없는 경우'
    한 번 더 위치를 물어볼지 결정하는 로직.
    """
    # 1) 출동이 아예 필요 없으면 재질문 X
    needs_visit = bool(summary_data.get("needs_visit") or needs_visit_flag)
    if not needs_visit:
        return False

    # 2) 텍스트/위치 정규화
    t = normalize(text)
    location = (summary_data.get("location") or "").strip()
    loc_norm = normalize(location) if location else ""

    # 3) "우리 집 / 집 앞 / 우리 동네 / 근처" 같은 애매한 표현 감지
    has_home_like_in_text = bool(re.search(HOME_LIKE_PATTERN, t))
    has_home_like_in_loc = bool(re.search(HOME_LIKE_PATTERN, loc_norm)) if loc_norm else False
    has_only_home_like = has_home_like_in_text or has_home_like_in_loc

    # 4) 동/리/아파트/정류장/역/학교/병원/공원 같은 "위치 단서" 감지
    has_location_word = bool(
        re.search(
            r"(동\s|\d+동\b|리\s|\d+리\b|길|로|아파트|빌라|마을회관|시장|버스정류장|정류장|역|학교|병원|공원)",
            t,
        )
    )

    # 5) 이미 '추가 위치 정보:' 턴이면 더 이상 재질문 X
    #    (두 번째 턴에서 다시 clarification으로 빠지는 걸 방지)
    if "추가위치정보" in t:
        return False

    # 6) 위치가 아예 없고, 위치 단서도 없으면 → 한 번은 꼭 물어본다
    #    예: "가로등이 나갔어", "도로에 뭐가 떨어져 있어요"
    if (not location) and (not has_location_word):
        return True

    # 7) 위치가 있긴 한데, '우리 집 앞 / 우리 동네 / 근처' 같은 표현 뿐이면 → 재질문
    #    예: "우리 집 앞에 가로등이 나갔어요"
    if has_only_home_like and not has_location_word:
        return True

    # 8) 그 외에는 과한 재질문 방지 → False
    return False


def build_clarification_response(
    text: str,
    category: str,
    needs_visit: bool,
    risk_level: str,
) -> Dict[str, Any]:
    """
    위치 정보 추가 질문용 clarification 응답.
    프론트 1·2·3 화면 구조가 깨지지 않도록
    tts_*와 answer_core 등을 채운다.
    """
    short_title = "추가 정보 확인"
    main_message = "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다."
    next_action_guide = (
        "예를 들어 ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요."
    )
    phone_suggestion = ""
    confirm_question = (
        "지금 화면에 보이는 내용이 맞다면 '결과 확인' 버튼을, "
        "아니라면 '재질문' 버튼을 눌러 다시 말씀해 주세요."
    )

    user_facing = {
        "short_title": short_title,
        "main_message": main_message,
        "next_action_guide": next_action_guide,
        "phone_suggestion": phone_suggestion,
        "confirm_question": confirm_question,
        # Clarification 단계이므로 아래 TTS는 “질문” 위주로
        "tts_listening": main_message + " " + next_action_guide,
        "tts_summary": main_message,
        "tts_result": "",
        "answer_core": "추가 위치 정보 확인이 필요합니다.",
    }

    staff_payload = {
        "summary": text,
        "category": f"{category}-위치추가요청",
        "location": "",
        "time_info": "",
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": "정확한 위치 확인 후 현장 조치 필요",
        "raw_keywords": extract_keywords(text),
        "memo_for_staff": "위치 정보가 부족하여 추가 질문 단계. 다음 턴에서 위치 정보가 보완될 예정입니다.",
    }

    return {
        "stage": "clarification",
        "minwon_type": category,
        "handling_type": "official_ticket" if needs_visit else "simple_guide",
        "need_call_transfer": False,
        "need_official_ticket": needs_visit,
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }


def build_user_facing(
    category: str,
    handling: Dict[str, Any],
    dept: Dict[str, str],
    text: str,
    staff_summary: str,
) -> Dict[str, str]:
    """
    주민에게 들려줄 멘트 + 각 화면(TTS)용 스크립트를 한 번에 구성.
    """
    handling_type = handling["handling_type"]
    need_call_transfer = handling["need_call_transfer"]
    need_official_ticket = handling["need_official_ticket"]

    empathy = "말씀해 주셔서 감사합니다. 많이 불편하셨겠습니다."

    short_title = f"{category} 관련 문의" if category != "기타" else "일반 문의"

    # 기본 main_message (결과 페이지 + 전반 안내용)
    main_message = f"{empathy} 지금 말씀해 주신 내용은 '{category}' 민원으로 보입니다."

    extra_pension = ""
    if category == "연금/복지":
        pm = build_pension_message(text)
        if pm:
            extra_pension = " " + pm

    next_action_guide = ""
    phone_suggestion = ""

    # handling_type에 따라 안내 멘트 구성
    if handling_type == "simple_guide":
        next_action_guide = summarize_for_user(text, category, handling)
        main_message = f"{empathy} 문의하신 내용은 {category} 관련 안내로 처리됩니다.{extra_pension}"
    elif handling_type == "contact_only":
        next_action_guide = summarize_for_user(text, category, handling)
        phone_suggestion = f"더 자세한 상담을 원하시면 {dept['name']}({dept['phone']})으로 연결해 드릴까요?"
    elif handling_type == "official_ticket":
        next_action_guide = (
            "말씀해 주신 내용을 바탕으로 담당 부서에 민원을 전달하겠습니다. "
            "담당자가 현장을 확인한 뒤 조치를 진행하게 됩니다."
        )

    if need_official_ticket:
        confirm_question = "이 내용으로 민원을 접수해 드릴까요?"
    else:
        confirm_question = "지금 안내해 드린 내용이 도움이 되셨나요?"

    # TTS 용 스크립트 구성
    tts_listening = (
        "말씀 잘 들었습니다. " + empathy +
        " 잠시 후, 민원 내용을 정리해서 안내해 드리겠습니다."
    )
    tts_summary = (
        f"지금까지 말씀하신 내용은 {short_title}로 정리됩니다. "
        "내용이 맞으시면 '결과 확인' 버튼을 눌러 주세요."
    )
    tts_result = main_message + " " + next_action_guide

    return {
        "short_title": short_title,
        "main_message": main_message,
        "next_action_guide": next_action_guide,
        "phone_suggestion": phone_suggestion,
        "confirm_question": confirm_question,
        "tts_listening": tts_listening,
        "tts_summary": tts_summary,
        "tts_result": tts_result,
        "answer_core": staff_summary or short_title,
    }


# ============================================================
#  LLM 래퍼들 (분류/요약/답변 생성)
# ============================================================

SYSTEM_PROMPT_CLASSIFIER = """
당신은 민원 분류 보조원입니다.
사용자의 발화를 보고 아래 카테고리 중 하나로 분류하고,
현장 출동(방문)이 필요한지 여부를 같이 판단해 주세요.

카테고리:
- 도로
- 시설물
- 연금/복지
- 심리지원
- 생활민원
- 기타

출동이 필요한 예:
- 도로 파손, 가로등 고장, 신호등 고장, 쓰러진 나무
- 전봇대, 전선, 감전 위험 등
출동이 필요하지 않은 예:
- 단순 서류 발급 문의, 연금 수령 나이 문의 등
"""

SYSTEM_PROMPT_ANSWER = """
당신은 고령층 주민을 위한 민원 안내 도우미입니다.
다음 규칙을 따르세요.

1) 말투는 존댓말, 짧고 쉬운 문장.
2) 최대한 구체적인 행동 안내를 포함.
3) 위험/안전 관련 내용이면, 신속한 신고/출동을 권장.
4) 규정/제도를 설명할 때는, 모르면 아는 범위까지만 말하고
   "자세한 내용은 담당 부서에 한 번 더 확인하시는 게 좋겠습니다."라고 덧붙입니다.
"""


def llm_classify_category_and_fieldwork(text: str, base_category: str) -> Dict[str, Any]:
    """
    LLM을 사용하여 카테고리 + 출장 필요 여부를 보정.
    """
    user_content = f"사용자 발화: {text}\n\n1) 카테고리와 2) 출동 필요 여부(True/False)를 JSON으로 답변해 주세요."
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_CLASSIFIER},
        {"role": "user", "content": user_content},
    ]
    resp = call_chat(
        model=MODEL,
        messages=messages,
        temperature=TEMP_CLASSIFIER,
    )
    try:
        data = json.loads(resp)
        category = data.get("category") or base_category
        needs_visit = bool(data.get("needs_visit", False))
    except Exception:
        category = base_category
        needs_visit = False
    return {"category": category, "needs_visit": needs_visit}


def llm_build_user_friendly_answer(
    text: str,
    category: str,
    handling: Dict[str, Any],
) -> str:
    """
    LLM을 사용하여 사용자가 이해하기 쉬운 안내 문장을 만든다.
    """
    user_content = f"사용자 민원 내용: {text}\n\n카테고리: {category}\nhandling: {handling}\n\n위 내용을 바탕으로 주민에게 들려줄 한 단락짜리 안내 문장을 만들어 주세요."
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ANSWER},
        {"role": "user", "content": user_content},
    ]
    resp = call_chat(
        model=MODEL,
        messages=messages,
        temperature=TEMP_GLOBAL,
    )
    return resp.strip()


# ============================================================
#  메인 파이프라인: run_pipeline_once
# ============================================================

def run_pipeline_once(text: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    텍스트 한 턴을 받아서
    - 시나리오 오버라이드
    - 규칙 기반 1차 분류
    - LLM 보정 분류
    - handling_type 결정
    - 요약/멘트 생성
    - clarification 여부 판단
    까지 한 번에 처리.
    """
    original_text = text.strip()
    if not original_text:
        return {
            "stage": "classification",
            "minwon_type": "기타",
            "handling_type": "simple_guide",
            "need_call_transfer": False,
            "need_official_ticket": False,
            "user_facing": {},
            "staff_payload": {},
        }

    # 1) 규칙 기반 1차 분류
    base_category, base_needs_visit = rule_first_classify(original_text)

    # 2) LLM 기반 카테고리/출장 필요 여부 보정
    cls = llm_classify_category_and_fieldwork(original_text, base_category)
    category = cls["category"]
    needs_visit = bool(cls["needs_visit"] or base_needs_visit)

    # 3) handling_type 기본 결정
    handling: Dict[str, Any] = {
        "handling_type": "simple_guide",
        "need_call_transfer": False,
        "need_official_ticket": False,
        "needs_visit": needs_visit,
        "risk_level": "보통",
    }

    if category in ("도로", "시설물"):
        handling["handling_type"] = "official_ticket"
        handling["need_official_ticket"] = True
        handling["needs_visit"] = True
        handling["risk_level"] = "긴급" if is_critical(original_text) else "보통"
    elif category in ("연금/복지", "심리지원"):
        handling["handling_type"] = "simple_guide"
        handling["need_call_transfer"] = True
    else:
        handling["handling_type"] = "simple_guide"

    # 4) 담당자용 요약 생성
    staff_summary_data = summarize_for_staff(original_text, category, handling)

    # 5) 추가 위치 정보 분리/보강
    analysis_text, additional_location = split_additional_location(original_text)
    if additional_location:
        loc = staff_summary_data.get("location") or ""
        if loc:
            new_loc = f"{loc}, 추가 위치: {additional_location}"
        else:
            new_loc = additional_location
        staff_summary_data["location"] = new_loc

    final_needs_visit = bool(staff_summary_data.get("needs_visit") or needs_visit)
    risk_level = handling["risk_level"]

    # 6) Clarification 여부 판단
    if need_clarification(staff_summary_data, category, analysis_text, final_needs_visit):
        return build_clarification_response(
            analysis_text,
            category,
            needs_visit=final_needs_visit,
            risk_level=risk_level,
        )

    # 7) 주민용 안내 멘트 구성
    dept_info = {
        "name": "민원 담당부서",
        "phone": "062-123-4567",
    }
    staff_summary_str = staff_summary_data.get("summary") or build_fallback_summary(
        original_text, category
    )
    user_facing = build_user_facing(
        category,
        handling,
        dept_info,
        analysis_text,
        staff_summary_str,
    )

    staff_payload = {
        "summary": staff_summary_str,
        "category": staff_summary_data.get("category", category),
        "location": staff_summary_data.get("location", ""),
        "time_info": staff_summary_data.get("time_info", ""),
        "risk_level": staff_summary_data.get("risk_level", risk_level),
        "needs_visit": staff_summary_data.get("needs_visit", final_needs_visit),
        "citizen_request": staff_summary_data.get("citizen_request", ""),
        "raw_keywords": staff_summary_data.get("raw_keywords", []),
        "memo_for_staff": staff_summary_data.get("memo_for_staff", ""),
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
