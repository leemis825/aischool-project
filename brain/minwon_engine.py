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

from .classifier import detect_minwon_type
from .summarizer import summarize_for_user, summarize_for_staff, build_fallback_summary

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
                "llm_needed": False,
                "reuse_last_result": True,
                "mode": "confirm_ok",
            }

        # 2-2. "아니요/틀렸어요" 계열 → 다시 요약부터
        if any(w in text_stripped for w in DENY_WORDS):
            return {
                "stage": "clarification",
                "llm_needed": True,
                "reuse_last_result": False,
                "mode": "confirm_reject",
            }

        # 2-3. 추가 설명(위치 보완 등) → 새 텍스트로 다시 요약
        return {
            "stage": "clarification",
            "llm_needed": True,
            "reuse_last_result": False,
            "mode": "add_detail",
        }

    # 3) 그 외 케이스는 안전하게 다시 clarification으로
    return {
        "stage": "clarification",
        "llm_needed": True,
        "reuse_last_result": False,
        "mode": "fallback",
    }


# -------------------- 카테고리 / 부서 매핑 --------------------
MINWON_TYPES = [
    "도로",
    "시설물",
    "연금/복지",
    "심리지원",
    "생활민원",
    "기타",
]

DEPT_MAP: Dict[str, Dict[str, str]] = {
    "도로": {
        "department_name": "도로관리팀",
        "contact": "062-123-1001",
        "reason": "도로 파손·낙석·가로수 등 도로 관련 민원",
    },
    "시설물": {
        "department_name": "시설관리팀",
        "contact": "062-123-1002",
        "reason": "가로등·공원·놀이터 등 공공시설 관련 민원",
    },
    "연금/복지": {
        "department_name": "복지·연금팀",
        "contact": "1355",
        "reason": "국민연금·기초연금·복지 서비스 문의",
    },
    "심리지원": {
        "department_name": "심리지원센터",
        "contact": "1577-0199",
        "reason": "우울·불안·심리상담 지원",
    },
    "생활민원": {
        "department_name": "생활민원팀",
        "contact": "062-123-1003",
        "reason": "생활 불편·청소·쓰레기 등 일반 민원",
    },
    "기타": {
        "department_name": "종합민원실",
        "contact": "062-123-1000",
        "reason": "기타/카테고리 미분류 민원",
    },
}

# -------------------- 공통 유틸/연금/LLM 래퍼 모듈 import --------------------
from .utils_text import (
    normalize,
    is_critical,
    extract_keywords,
    split_additional_location,
)
from .rules_pension import compute_pension_age, build_pension_message
from .llm_client import call_chat, MODEL, TEMP_GLOBAL, TEMP_CLASSIFIER


# ============================================================
#  시나리오 1·2·3용 규칙 오버라이드 레이어
# ============================================================
def detect_scenario_override(text: str) -> Optional[Dict[str, Any]]:
    """
    특정 시나리오(데모용 3개 케이스)에 대해
    LLM이 이상하게 분류해도 항상 원하는 쪽으로 떨어지게 하는 규칙.
    """
    t = normalize(text).replace(" ", "")

    # 🔸 시나리오 1: 집 앞/우리 집 + 나무가 쓰러져서 통행/대문 문제
    has_tree = "나무" in t and ("쓰러져" in t or "쓰러졌" in t)
    has_home = ("우리집" in t) or ("집앞" in t) or ("집앞에" in t)
    has_pass_issue = ("통행이불편" in t) or ("지나가기불편" in t) or ("대문" in t)

    if has_tree and (has_home or has_pass_issue):
        return {
            "scenario": 1,
            "category": "도로",
            "needs_visit": True,
            "risk_level": "긴급",
            "handling_type": "official_ticket",
            "need_official_ticket": True,
            "need_call_transfer": False,
        }

    # 시나리오 2: 1999년생인데 연금 언제 받아?
    if "1999년생" in t and "연금" in t:
        return {
            "scenario": 2,
            "category": "연금/복지",
            "needs_visit": False,
            "risk_level": "경미",
            "handling_type": "simple_guide",
            "need_official_ticket": False,
            "need_call_transfer": True,
        }

    # 시나리오 3: 우울 + 죽고 싶/자살
    if "우울" in t and ("죽고싶" in t or "자살" in t):
        return {
            "scenario": 3,
            "category": "심리지원",
            "needs_visit": False,
            "risk_level": "긴급",
            "handling_type": "contact_only",
            "need_official_ticket": False,
            "need_call_transfer": True,
        }

    return None



# -------------------- 규칙 우선 1차 분류 --------------------
def rule_first_classify(text: str) -> Tuple[str, bool]:
    """
    1차 카테고리 분류.

    1) classifier.detect_minwon_type 로 상위 카테고리 우선 결정
    2) 거기서 '기타'가 나온 경우에만 기존 정규식 기반 분류를 사용
    returns: (category, needs_visit)
    """

    # 1단계: classifier 기반 상위 카테고리
    primary = detect_minwon_type(text)
    if primary != "기타":
        needs_visit_map = {
            "도로": True,
            "시설물": True,
            "연금/복지": False,
            "심리지원": False,
            "생활민원": False,
        }
        return primary, needs_visit_map.get(primary, False)

    # 2단계: 기존 정규식 규칙 (백업)
    t = normalize(text)

    # 도로
    if re.search(r"도로|길바닥|포장도로|아스팔트|구멍|파였|패인", t):
        return "도로", True

    # 시설물
    if re.search(r"가로등|신호등|전봇대|전주|놀이터|그네|미끄럼틀|공원|벤치", t):
        return "시설물", True

    # 연금/복지
    if re.search(r"연금|기초연금|국민연금|기초 생활|수당|장려금", t):
        return "연금/복지", False

    # 심리지원
    if re.search(r"우울|불안|우울증|공황|상담 받고 싶", t):
        return "심리지원", False

    # 소음/생활민원
    if re.search(r"소음|시끄럽|담배냄새|악취|쓰레기|무단투기", t):
        return "생활민원", False

    # 치안/안전
    if re.search(r"싸움|폭행|위협|스토킹", t):
        return "생활민원", False

    # 그 외
    return "기타", False


# -------------------- LLM: 카테고리 + 출동 여부 + 위험도 --------------------
def llm_classify_category_and_fieldwork(
    text: str,
    base_category: str,
) -> Dict[str, Any]:
    """
    LLM으로 카테고리 + 출동 여부 + 위험도까지 한 번에 판단.
    """
    system = """너는 민원 상담 도우미야.
다음 민원 내용을 보고 다음 필드를 JSON으로만 출력해.

{
  "category": "도로" | "시설물" | "연금/복지" | "심리지원" | "생활민원" | "기타",
  "needs_visit": true | false,
  "risk_level": "긴급" | "보통" | "경미"
}

- category는 base_category 후보를 참고하되 더 적절하면 바꿔도 됨.
- needs_visit는 '현장에 가서 직접 봐야 할 것 같으면' true.
- 위험도가 매우 높거나 생명/안전에 관련되면 risk_level은 '긴급'.
"""
    user = f"""
민원 내용:
\"\"\"{text}\"\"\"\

규칙 기반으로 추정한 1차 카테고리 후보: {base_category}
이 후보를 참고하되, 더 적절한 카테고리가 있으면 바꿔도 돼.
""".strip()

    out = call_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=MODEL,
        temperature=TEMP_CLASSIFIER,
        max_tokens=200,
    )

    try:
        data = json.loads(out)
    except Exception:
        return {
            "category": base_category,
            "needs_visit": False,
            "risk_level": "보통",
        }

    category = data.get("category") or base_category
    needs_visit = bool(data.get("needs_visit", False))
    risk_level = data.get("risk_level", "보통")

    if category not in MINWON_TYPES:
        category = base_category

    return {
        "category": category,
        "needs_visit": needs_visit,
        "risk_level": risk_level,
    }

# -------------------- handling_type / 접수 방식 결정 --------------------
def decide_handling_from_struct(
    category: str,
    needs_visit: bool,
    risk_level: str,
    text: str,
) -> Dict[str, Any]:
    handling_type = "simple_guide"
    need_call_transfer = False
    need_official_ticket = False

    # 매우 긴급 + 출동 필요 → 바로 공문 접수
    if is_critical(text) and needs_visit:
        return {
            "handling_type": "official_ticket",
            "need_call_transfer": False,
            "need_official_ticket": True,
            "risk_level": risk_level,
            "needs_visit": needs_visit,
        }

    if category == "심리지원":
        handling_type = "contact_only"
        need_call_transfer = True
        need_official_ticket = False

    elif category == "연금/복지":
        handling_type = "simple_guide"
        need_call_transfer = True
        need_official_ticket = False

    elif needs_visit:
        handling_type = "official_ticket"
        need_call_transfer = False
        need_official_ticket = True

    return {
        "handling_type": handling_type,
        "need_call_transfer": need_call_transfer,
        "need_official_ticket": need_official_ticket,
        "risk_level": risk_level,
        "needs_visit": needs_visit,
    }


# -------------------- clarification 필요 여부 판단 --------------------
def need_clarification(
    summary_data: Dict[str, Any],
    category: str,
    text: str,
    needs_visit_flag: bool,
) -> bool:
    ...
    # 1) 출동이 아예 필요 없으면 재질문 X
    needs_visit = bool(summary_data.get("needs_visit") or needs_visit_flag)
    if not needs_visit:
        return False

    # 2) 이미 위치가 채워져 있으면 재질문 X
    #    🔸 단, '우리 집', '집 앞'처럼 애매한 표현만 있으면 여전히 재질문
    location = (summary_data.get("location") or "").strip()
    if location:
        loc_norm = normalize(location)
        only_home_like = bool(
            re.search(r"우리집|집앞|집앞에|우리집앞|집앞골목|집앞 골목", loc_norm)
        )
        if not only_home_like:
            return False
        # only_home_like 인 경우에는 '주소가 애매하다'고 보고
        # 아래 로직으로 넘어가서 True가 나올 수 있게 함

    # 3) 텍스트 안에 위치 관련 단어가 포함되어 있는지(대략적인 감지)
    t = normalize(text)

    # '우리 집' / '집 앞'만 있는 경우는 애매한 위치로 간주
    has_only_home = bool(re.search(r"우리집|집앞", t))

    # 주소/지명 키워드
    has_location_word = bool(
        re.search(r"동|리|길|로|아파트|빌라|마을회관|마을|시장|버스정류장", t)
    )

    # 4) 추가 위치정보 마커: 이게 붙으면 "위치 턴"으로 보고 더 이상 재질문 X
    has_additional_marker = "추가위치정보" in t
    if has_additional_marker:
        return False

    # 5) 첫 턴에서 '우리 집', '집 앞'만 있고, 주소는 없으면 재질문
    if has_only_home and not has_location_word:
        return True

    # 6) 그 외에는 과한 재질문 방지 → False
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
    tts_*와 answer_core도 함께 내려준다.
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
        # ListeningPage
        "tts_listening": (
            "말씀해 주셔서 감사합니다. "
            "현장 출동을 위해 정확한 위치가 필요합니다. "
            "이어서 위치를 조금 더 자세히 말씀해 주세요."
        ),
        # SummaryPage
        "tts_summary": (
            f"지금 말씀해 주신 내용은 {category} 민원으로 보입니다. "
            "현장에 나가기 위해 정확한 위치 정보가 더 필요해서 "
            "추가로 위치를 한 번만 더 여쭤보고 있습니다. "
            "예를 들어, ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요."
        ),
        # ResultPage (clarification 단계에서는 요약과 거의 동일)
        "tts_result": main_message + " " + next_action_guide,
        # SummaryPage에서 크게 보여줄 한 줄
        "answer_core": "정확한 위치를 한 번 더 여쭤보고 있습니다.",
    }

    staff_payload = {
        "summary": text[:120] + ("..." if len(text) > 120 else ""),
        "category": category,
        "location": "",
        "time_info": "",
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": "",
        "raw_keywords": extract_keywords(text),
        "memo_for_staff": (
            "위치 정보 부족으로 추가 질문 필요. "
            "내용상 현장 출동이 필요해 보이는 민원일 수 있음."
        ),
    }

    return {
        "stage": "clarification",
        "minwon_type": category,
        "handling_type": "official_ticket" if needs_visit else "contact_only",
        "need_call_transfer": True,
        "need_official_ticket": needs_visit,
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }

def user_facing_scenario1_tree(dept: Dict[str, str]) -> Tuple[str, str, str]:
    """
    시나리오 1: 집 앞 나무 쓰러짐 (도로/시설물 + 방문 필요)
    return: (main_message, next_action_guide, phone_suggestion)
    """
    # ✅ 결과 화면(3번)에선 '어떻게 처리될지'만 보여주도록 조치 문장만 남김
    main_message = (
        "담당 부서에서 현장을 방문해 상황을 확인한 뒤 조치를 진행할 예정입니다."
    )
    next_action_guide = (
        "담당자가 현장 상황을 확인한 후에 필요한 안전 조치와 정리를 진행하게 됩니다. "
        "현장 방문 시 주변에 위험이 될 만한 물건이 있으면 미리 치워 두시면 좋습니다."
    )
    phone_suggestion = (
        f"추가로 궁금한 점이 있으시면 {dept['department_name']} "
        f"({dept['contact']})으로 문의해 주셔도 됩니다."
    )
    return main_message, next_action_guide, phone_suggestion


def user_facing_scenario2_pension(pension_msg: str, dept: Dict[str, str]) -> Tuple[str, str, str]:
    """
    시나리오 2: 연금 나이 문의
    """
    main_message = pension_msg or (
        "말씀해 주신 내용은 연금/복지 관련 문의로 보입니다. "
        "정확한 수급 시기와 금액은 국민연금공단이나 주민센터에서 최종 확인해 주시는 것이 좋습니다."
    )
    next_action_guide = (
        f"보다 자세한 안내가 필요하시면 {dept['department_name']}이나 "
        f"{dept['contact']} 번호로 문의해 보셔도 좋습니다."
    )
    phone_suggestion = (
        "국민연금공단 고객센터(1355)로 연락하시면, 연금 예상 수령 시기와 "
        "금액에 대해 자세한 상담을 받으실 수 있습니다."
    )
    return main_message, next_action_guide, phone_suggestion


def user_facing_scenario3_mental(dept: Dict[str, str]) -> Tuple[str, str, str]:
    """
    시나리오 3: 심리지원(우울/자살 생각)
    """
    main_message = (
        "요즘 많이 힘드신 것 같아요. 혼자 감당하지 않으셔도 됩니다. "
        "가까운 심리지원센터에서 전문 상담을 받으실 수 있습니다."
    )
    next_action_guide = (
        f"가능하시면 {dept['contact']} 번호로 연락하시거나, "
        "거주지 인근 보건소·정신건강복지센터에 상담을 요청해 보시는 것도 좋겠습니다. "
        "생명이 즉시 위험한 상황이라면 지체하지 말고 112 또는 119에 바로 도움을 요청해 주세요."
    )
    phone_suggestion = (
        f"지금 바로 도움이 필요하시다면, {dept['contact']} 또는 112·119에 연락해 주세요."
    )
    return main_message, next_action_guide, phone_suggestion

# -------------------- user_facing 생성 --------------------
def build_user_facing(
    category: str,
    handling: Dict[str, Any],
    dept: Dict[str, str],
    text: str,
    staff_summary: str,
) -> Dict[str, Any]:
    handling_type = handling["handling_type"]
    need_call_transfer = handling["need_call_transfer"]
    need_official_ticket = handling["need_official_ticket"]

    empathy = "말씀해 주셔서 감사합니다. 많이 불편하셨겠습니다."
    short_title = f"{category} 관련 문의" if category != "기타" else "일반 문의"

    # 시나리오 다시 감지 (텍스트만으로도 동일하게 잡히도록)
    scenario_info = detect_scenario_override(text)
    scenario_id = scenario_info["scenario"] if scenario_info else None

    # 기본값 초기화
    main_message = ""
    next_action_guide = ""
    phone_suggestion = ""

    # 🔹 연금용 추가 문구
    pension_msg = ""
    if category == "연금/복지":
        pension_msg = build_pension_message(text) or ""

    # 1) 시나리오별 우선 템플릿
    if scenario_id == 1:
        # 나무(도로/시설물, 방문 필요)
        main_message, next_action_guide, phone_suggestion = \
            user_facing_scenario1_tree(dept)

    elif scenario_id == 2:
        # 연금
        main_message, next_action_guide, phone_suggestion = \
            user_facing_scenario2_pension(pension_msg, dept)

    elif scenario_id == 3:
        # 심리지원
        main_message, next_action_guide, phone_suggestion = \
            user_facing_scenario3_mental(dept)

    # 2) 그 외 일반 규칙 (시나리오가 없을 때만 사용)
    if scenario_id is None:
        if category == "연금/복지":
            main_message = pension_msg or (
                "말씀해 주신 내용은 연금/복지 관련 문의로 보입니다. "
                "정확한 수급 시기와 금액은 국민연금공단이나 주민센터에서 한 번 더 확인해 주세요."
            )
            next_action_guide = (
                "연금을 언제부터 얼마나 받을 수 있는지, "
                "구체적인 금액은 국민연금공단 고객센터(1355)를 통해 확인하실 수 있습니다."
            )
            phone_suggestion = (
                "궁금한 점이 더 있으시면 국민연금공단(1355) 또는 가까운 주민센터로 문의해 주세요."
            )

        elif category == "심리지원":
            main_message = (
                "요즘 마음이 많이 힘드신 것 같아요. 혼자 감당하지 않으셔도 됩니다. "
                "가까운 심리지원센터에서 전문 상담을 받아 보시는 것을 권해 드립니다."
            )
            next_action_guide = (
                "주민센터나 보건소에 문의하시면 심리 상담 서비스를 연계받으실 수 있고, "
                "필요시 정신건강복지센터와도 연결해 드립니다."
            )
            phone_suggestion = (
                "생명이 즉시 위험한 상황이라면 지체하지 말고 112 또는 119에 바로 도움을 요청해 주세요."
            )

        elif handling_type == "official_ticket":
            main_message = (
                "말씀해 주신 내용은 공공 시설이나 도로와 관련된 민원으로 보입니다. "
                "담당 부서에서 현장을 방문해 상황을 확인한 뒤 조치를 진행할 예정입니다."
            )
            next_action_guide = (
                "현장 확인 후에는 정리·보수 작업이 진행되며, 필요한 경우 추가 안내를 드리겠습니다."
            )
            phone_suggestion = (
                f"진행 상황이 궁금하시면 {dept['department_name']} "
                f"({dept['contact']})으로 문의해 주세요."
            )

        elif handling_type == "contact_only":
            main_message = (
                "말씀해 주신 내용은 전화 상담을 통해 좀 더 자세히 안내받으시는 것이 좋겠습니다."
            )
            next_action_guide = (
                f"{dept['department_name']}에 전화하시면 상황에 맞는 상담과 지원 방법을 "
                "안내받으실 수 있습니다."
            )
            phone_suggestion = f"연락처는 {dept['contact']} 입니다."

        else:  # simple_guide 등
            main_message = (
                f"지금 말씀해 주신 내용은 '{category}' 관련 일반 문의로 보입니다."
            )
            next_action_guide = (
                "간단한 안내로 해결될 수 있는 내용이며, 추가로 궁금하신 점이 있으면 언제든지 말씀해 주세요."
            )
            phone_suggestion = ""

    # 🔹 Summary 화면용 핵심 한 줄(answer_core)
    user_summary_core = summarize_for_user(text, category)

    if category == "연금/복지":
        answer_core = pension_msg or user_summary_core
    elif category == "심리지원":
        answer_core = (
            "마음이 많이 힘드신 것 같아요. 도움이 필요하시면 언제든지 말씀해 주세요."
        )
    elif handling_type == "official_ticket":
        answer_core = (
            "말씀해 주신 내용은 공공 시설과 관련된 민원으로, "
            "현장 확인과 방문 조치가 필요한 상황으로 보입니다."
        )
    else:
        answer_core = user_summary_core or main_message

    # 🔹 TTS 문장들
    tts_listening = (
        f"{empathy} 지금 말씀해 주신 내용을 잘 들었습니다. "
        "잠시만 기다려 주시면 내용을 정리해 드리겠습니다."
    )

    tts_summary = (
        f"지금 말씀해 주신 내용은 {category} 관련 민원으로 이렇게 이해했습니다. "
        f"{user_summary_core} 이 내용이 맞으시면 '결과 확인' 버튼을, "
        "다르면 '재질문' 버튼을 눌러 다시 말씀해 주세요."
    )

    joined_parts = " ".join(
        part for part in [answer_core, main_message, next_action_guide, phone_suggestion] if part
    ).strip()
    tts_result = joined_parts or answer_core

    return {
        "short_title": short_title,
        "main_message": main_message,
        "next_action_guide": next_action_guide,
        "phone_suggestion": phone_suggestion,
        "confirm_question": "화면에 보이는 내용이 질문하신 내용과 맞다면 '결과 확인' 버튼을 눌러 주세요.",
        "tts_listening": tts_listening,
        "tts_summary": tts_summary,
        "tts_result": tts_result,
        "answer_core": answer_core,
    }


    # ---------- TTS 스크립트 구성 ----------
    tts_listening = (
        f"{empathy} 지금 말씀해 주신 내용을 한 번 정리해 보겠습니다."
    )

    tts_summary = (
        f"지금 말씀해 주신 내용을 이렇게 이해했습니다. "
        f"{user_summary_core} "
        "화면의 내용이 맞으면 결과 확인 버튼을, 다르면 재질문 버튼을 눌러 주세요."
    )

    joined_parts = " ".join(
        part for part in [main_message, next_action_guide, phone_suggestion] if part
    ).strip()
    tts_result = joined_parts or main_message

    # ---------- SummaryPage에 크게 보여줄 한 줄(질문 요약) ----------
    # 연금/복지도 '질문 정리'가 나오도록, pension_msg로 덮어쓰지 않는다.
    answer_core = user_summary_core

    return {
        "short_title": short_title,
        "main_message": main_message,
        "next_action_guide": next_action_guide,
        "phone_suggestion": phone_suggestion,
        "confirm_question": confirm_question,
        "tts_listening": tts_listening,
        "tts_summary": tts_summary,
        "tts_result": tts_result,
        "answer_core": answer_core,
    }


# -------------------- staff_payload 생성 --------------------
def extract_citizen_request(text: str) -> str:
    system = (
        "다음 민원 문장에서 주민이 실제로 원하는 조치(요청 사항)를 한 문장으로 요약해줘. "
        "예: '쓰러진 나무를 치워 달라는 요청' 처럼.\n"
        "가능하면 '...해 달라는 요청' 형식으로 끝나게 작성해."
    )
    out = call_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=80,
    )
    return out or ""


def build_staff_payload(
    summary_data: Dict[str, Any],
    category: str,
    handling: Dict[str, Any],
    text: str,
) -> Dict[str, Any]:
    location = summary_data.get("location") or ""
    time_info = summary_data.get("time_info", "")
    risk_level = handling["risk_level"]
    needs_visit = bool(summary_data.get("needs_visit") or handling["needs_visit"])

    citizen_request = extract_citizen_request(text)

    return {
        "summary": summary_data.get("summary_3lines", ""),
        "category": category,
        "location": location,
        "time_info": time_info,
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": citizen_request,
        "raw_keywords": extract_keywords(text),
        "memo_for_staff": "",
    }


# -------------------- 메인 파이프라인 --------------------
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

    # 1) 데모 시나리오 오버라이드
    scenario = detect_scenario_override(original_text)
    if scenario:
        category = scenario["category"]
        needs_visit = scenario["needs_visit"]
        risk_level = scenario["risk_level"]
    else:
        # 2) 규칙 기반 1차 분류
        base_category, base_needs_visit = rule_first_classify(original_text)
        # 3) LLM 보정 분류
        cls = llm_classify_category_and_fieldwork(original_text, base_category)
        category = cls["category"]
        needs_visit = cls["needs_visit"] or base_needs_visit
        risk_level = cls["risk_level"]

    # 4) handling_type 결정
    handling = decide_handling_from_struct(
        category, needs_visit, risk_level, original_text
    )

    # 5) 부서 정보
    dept = DEPT_MAP.get(category, DEPT_MAP["기타"])

    # 6) 위치 추가 정보 분리
    analysis_text, extra_location = split_additional_location(original_text)

    # 7) 담당자용 요약
    summary_data = summarize_for_staff(analysis_text, category)

    # 8) split_additional_location 결과를 location에 반영
    if extra_location and not (summary_data.get("location") or "").strip():
        summary_data["location"] = extra_location

    # 9) needs_visit 최종 보정
    final_needs_visit = bool(summary_data.get("needs_visit") or handling["needs_visit"])
    handling["needs_visit"] = final_needs_visit

    # 10) 🔥 출동 필요 + 위치 애매하면 'clarification' 단계로 한 번 더 물어보기
    if need_clarification(summary_data, category, analysis_text, final_needs_visit):
        return build_clarification_response(
            analysis_text,
            category,
            needs_visit=final_needs_visit,
            risk_level=risk_level,
        )

    # 11) staff_payload / user_facing 생성
    staff_payload = build_staff_payload(summary_data, category, handling, analysis_text)
    staff_summary = staff_payload["summary"]

    user_facing = build_user_facing(
        category,
        handling,
        dept,
        analysis_text,
        staff_summary,
    )

    # 12) stage 결정
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
