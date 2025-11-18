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
    "confirm_question": str
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

import os
import re
import json
from typing import Any, Dict, List, Tuple, Optional  # >>> Optional 추가

from dotenv import load_dotenv
from openai import OpenAI

# -------------------- 환경 설정 --------------------
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다.")

client = OpenAI(api_key=API_KEY)

MODEL = "gpt-4o"
TEMP_GLOBAL = 0.2      # 요약/멘트/라우팅 등
TEMP_CLASSIFIER = 0.0  # 분류/출동 여부 판단 (결정적)


# -------------------- 카테고리 / 부서 매핑 --------------------
MINWON_TYPES = [
    "도로", "시설물", "연금/복지", "심리지원", "생활민원", "기타"
]

DEPT_MAP: Dict[str, Dict[str, str]] = {
    "도로": {
        "department_name": "도로관리팀",
        "contact": "062-123-1001",
        "reason": "도로 파손·낙석·가로수 등 도로 관련 민원"
    },
    "시설물": {
        "department_name": "시설관리팀",
        "contact": "062-123-1002",
        "reason": "가로등·공원·놀이터 등 공공시설 관련 민원"
    },
    "연금/복지": {
        "department_name": "복지·연금팀",
        "contact": "1355",
        "reason": "국민연금·기초연금·복지 서비스 문의"
    },
    "심리지원": {
        "department_name": "심리지원센터",
        "contact": "1577-0199",
        "reason": "우울·불안·심리상담 지원"
    },
    "생활민원": {
        "department_name": "생활민원팀",
        "contact": "062-123-1003",
        "reason": "생활 불편·청소·쓰레기 등 일반 민원"
    },
    "기타": {
        "department_name": "종합민원실",
        "contact": "062-123-1000",
        "reason": "기타/카테고리 미분류 민원"
    },
}

# -------------------- 위험 키워드 / 정규화 --------------------
CRITICAL_PATTERNS = [
    r"쓰러지", r"넘어가", r"붕괴", r"무너졌",
    r"전선", r"감전", r"불 ?났", r"화재", r"폭발",
    r"피가", r"폭행", r"위협", r"자살", r"죽고 싶"
]

NORMALIZE_MAP = {
    "전봇대": "전주",
    "길바닥": "도로",
    "차도": "도로",
    "보도블럭": "보도블록",
    "쓰러진 나무": "가로수 쓰러짐",
    "나무가 쓰러져": "가로수 쓰러짐",
}

# -------------------- 국민연금 출생연도별 지급 개시 연령 --------------------
PENSION_RULES = [
    {"start": 1953, "end": 1956, "old_age": 61, "early": 56},
    {"start": 1957, "end": 1960, "old_age": 62, "early": 57},
    {"start": 1961, "end": 1964, "old_age": 63, "early": 58},
    {"start": 1965, "end": 1968, "old_age": 64, "early": 59},
    {"start": 1969, "end": 9999, "old_age": 65, "early": 60},
]


def compute_pension_age(birth_year: int, kind: str = "old") -> int:
    """출생연도에 따른 노령/조기노령 개시연령 반환."""
    for row in PENSION_RULES:
        if row["start"] <= birth_year <= row["end"]:
            return row["old_age"] if kind == "old" else row["early"]
    return 65


# -------------------- 공통 유틸 --------------------
def normalize(text: str) -> str:
    t = text.strip()
    for k, v in NORMALIZE_MAP.items():
        t = t.replace(k, v)
    return t


def is_critical(text: str) -> bool:
    t = normalize(text)
    for pat in CRITICAL_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def extract_keywords(text: str, max_k: int = 5) -> List[str]:
    tokens = re.split(r"[,\s\.]+", text)
    tokens = [w for w in tokens if len(w) >= 2]
    uniq = []
    for w in tokens:
        if w not in uniq:
            uniq.append(w)
    return uniq[:max_k]


def call_chat(messages: List[Dict[str, str]],
              model: str = MODEL,
              temperature: float = TEMP_GLOBAL,
              max_tokens: int = 512) -> str:
    """OpenAI Chat 호출 래퍼."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("[WARN] OpenAI API error:", e)
        return ""


# ============================================================
#  시나리오 1·2·3용 규칙 오버라이드 레이어  (가장 중요!)
# ============================================================

def detect_scenario_override(text: str) -> Optional[Dict[str, Any]]:
    """
    특정 시나리오(데모용 3개 케이스)에 대해
    LLM이 이상하게 분류해도 항상 원하는 쪽으로 떨어지게 하는 규칙.

    반환 예:
    {
      "scenario": 1,
      "category": "도로",
      "needs_visit": True,
      "risk_level": "긴급",
      "handling_type": "official_ticket",
      "need_official_ticket": True
    }
    """
    t = normalize(text).replace(" ", "")

    # --- 시나리오 1: 나무가 쓰러져 집 앞/골목 막음 → 도로 + 방문 필요 + 긴급 ---
    if ("나무" in t or "가로수" in t) and \
       ("쓰러" in t) and \
       ("집앞" in t or "대문" in t or "골목" in t or "마을회관" in t):
        return {
            "scenario": 1,
            "category": "도로",
            "needs_visit": True,
            "risk_level": "긴급",
            "handling_type": "official_ticket",
            "need_official_ticket": True,
        }

    # --- 시나리오 2: 출생연도 + 국민연금 문의 → 연금/복지 + simple_guide ---
    if ("연금" in t or "국민연금" in t) and re.search(r"19[5-9]\d년생", text):
        return {
            "scenario": 2,
            "category": "연금/복지",
            "needs_visit": False,
            "risk_level": "경미",
            "handling_type": "simple_guide",
            "need_official_ticket": False,
            "need_call_transfer": True,  # 상담 전화 제안
        }

    # --- 시나리오 3: 우울 + 잠 문제 + 상담 요청 → 심리지원 + 전화 연결 ---
    if (("우울" in t) or ("힘들" in t) or ("잠도잘못자" in t) or ("잠도잘못잤" in t) or ("잠이안와" in t)) and \
       ("상담" in t or "얘기" in t or "이야기" in t):
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
    규칙 기반 1차 분류.
    반환: (minwon_type, needs_visit_rule)
    needs_visit_rule: 규칙 기준으로 '출동 필요해 보이는가' 여부.
    """
    t = normalize(text)

    # 심리지원
    if re.search(r"우울|불안|잠이 안|죽고 싶|괴로워", t):
        return "심리지원", False

    # 연금/복지
    if re.search(r"연금|국민연금|기초연금|복지|수급자", t):
        return "연금/복지", False

    # 도로
    if re.search(r"도로|길이|포트홀|구멍|보도블록|보도블럭|맨홀", t):
        return "도로", True

    # 시설물
    if re.search(r"가로등|신호등|공원|벤치|놀이터|체육시설|건물", t):
        return "시설물", True

    # 소음/생활민원
    if re.search(r"소음|시끄럽|담배냄새|악취|쓰레기|무단투기", t):
        return "생활민원", False

    # 치안 비슷한 표현
    if re.search(r"싸움|폭행|위협|스토킹", t):
        return "생활민원", False

    # 규칙에 안 걸리면 기타
    return "기타", False


# -------------------- LLM: 카테고리 + 출동 여부 + 위험도 --------------------
def llm_classify_category_and_fieldwork(text: str,
                                        base_category: str) -> Dict[str, Any]:
    """
    LLM으로 카테고리 + 출동 여부 + 위험도까지 한 번에 판단.
    규칙 기반 base_category를 힌트로 주고, 최종 category는 LLM이 확정.
    """

    system = """
너는 한국 지자체 민원 분류/출동판단을 돕는 어시스턴트야.

[전체 역할]
- 주민이 말한 민원 내용을 보고,
  ① 어떤 카테고리(부서 계열)에 속하는지,
  ② 현장 출동(방문) 필요 여부(needs_visit),
  ③ 위험도(risk_level)
  를 한 번에 판단하는 역할이야.

[입력 정보]
- 민원 내용: 주민이 말한 자연어 문장
- base_category: 규칙 기반으로 1차 추정한 카테고리(힌트용)
  * base_category는 참고용이며, 더 적절한 카테고리가 있으면 바꿔도 돼.
  * 다만 명백한 근거가 없다면 base_category를 유지하는 쪽을 우선 고려해.

--------------------------------------------------
1단계: 카테고리 결정

다음 6개 카테고리 중 "가장 적절한 하나"만 고르기.
  - 도로
  - 시설물
  - 연금/복지
  - 심리지원
  - 생활민원
  - 기타

[카테고리 정의 및 예시]

1) 도로
  - 차도, 인도, 골목길, 마을길, 자전거도로, 주차장 바닥, 비포장도로, 맨홀, 배수로 등
  - 예) "도로에 구멍 났어요", "집 앞 길이 파였어요", "맨홀 뚜껑이 깨졌어요"

2) 시설물
  - 건물(마을회관, 경로당 등), 공공시설, 가로등, 신호등, CCTV, 놀이터 시설, 체육시설, 공원 시설, 정자, 울타리, 난간 등
  - 예) "가로등이 안 켜져요", "놀이터 그네가 부러졌어요"

3) 연금/복지
  - 국민연금, 기초연금, 장애인연금, 각종 복지급여, 기초생활수급, 긴급복지, 돌봄 서비스, 장기요양보험, 경로우대 등
  - 예) "기초연금 신청은 어떻게 해요?", "기초생활수급 자격이 궁금해요"

4) 심리지원
  - 우울, 불안, 스트레스, 외로움, 불면, 가족/대인관계로 인한 정서적 고통
  - 자살·자해·죽고 싶다·살 맛이 안 난다 등 심각한 표현 포함
  - 예) "요즘 너무 우울해서 아무것도 하기 싫어요", "죽고 싶다는 생각이 계속 나요"

5) 생활민원
  - 쓰레기, 불법투기, 소음, 악취, 해충, 가축·반려동물 관련, 불편 신고 등 생활환경 전반
  - 단, 뚜렷하게 도로나 시설물 문제가 아니면서, 일상 불편을 호소하는 내용
  - 예) "밤마다 술집에서 시끄러워요", "쓰레기를 자꾸 버려요"

6) 기타
  - 위 5개 중 어디에도 뚜렷하게 맞지 않거나, 내용이 너무 모호한 경우
  - 예) "그냥 좀 불편해요" 처럼 구체적인 사안이 없는 경우

[카테고리 선택 기준]
- base_category가 상식적으로 타당하면 그대로 사용해.
- 하지만 민원 내용이 위 정의와 명백히 다르면, base_category를 무시하고 더 적절한 카테고리로 변경해.
- 어떤 카테고리에도 분류하기 애매하면 "기타"를 선택해.

--------------------------------------------------
2단계: 현장 출동 필요 여부(needs_visit) 판단

needs_visit는 "현장에 사람이 직접 나가서 확인/조치가 필요한지"를 의미해.
- true  : 출동·현장 확인이 필요한 경우
- false : 전화/행정처리/안내만으로 처리 가능한 경우

[출동 필요성 판단 규칙]

(1) 기본 규칙
  - 물리적인 시설·환경에 문제가 있으면 기본적으로 needs_visit=true를 우선 고려.
  - 단순 문의·절차 안내, 서류 발급 문의 등은 needs_visit=false.

(2) 출동을 강하게 권장해야 하는 키워드/상황 (안전 보수적 판단)
  - 나무 쓰러짐, 가로수/나무 넘어짐
  - 전선, 전기, 감전 위험
  - 도로 파임, 싱크홀, 큰 구멍, 포트홀
  - 맨홀 뚜껑 분실/파손, 배수로 뚜껑 문제
  - 건물·담장·옹벽 붕괴, 균열, 낙석, 붕괴 위험
  - 도로나 인도, 통행로를 막고 있는 큰 장애물
  → 위에 해당하면 웬만하면 needs_visit=true로 판단.

(3) 카테고리별 기본 경향
  - 도로, 시설물
    · 물리적 상태 점검이 필요한 내용이면 needs_visit=true가 기본.
    · 단순 문의(예: "도로점용 허가가 어떻게 되나요?")는 needs_visit=false.
  - 연금/복지
    · 대부분 상담·안내가 우선 → 보통 needs_visit=false.
  - 심리지원
    · 상담·연결이 우선 → needs_visit=false로 두되, 매우 심각한 표현이 있어도
      "현장출동"보다는 별도 상담·지원으로 연결된다고 가정.
  - 생활민원
    · 쓰레기 수거, 불법투기 현장 확인, 소음·악취의 현장 확인 등은 needs_visit=true 가능.
    · 단순 제도·문의·상담은 needs_visit=false.
  - 기타
    · 내용이 모호하면 우선 needs_visit=false를 기본으로 두되,
      "즉각적인 물리적 위험"이 연상되는 표현이 있으면 예외적으로 true.

--------------------------------------------------
3단계: 위험도(risk_level) 판단

risk_level은 아래 3개 중 하나만 선택해.
  - "긴급"
  - "보통"
  - "경미"

[위험도 정의]

1) "긴급"
  - 사람의 생명·신체에 직접적이고 즉각적인 위험이 있을 수 있는 경우.
  - 예)
    · 쓰러진 나무·구조물이 도로를 막아 차량·보행자 사고 위험이 큰 경우
    · 전선이 늘어져 있거나 감전 가능성이 있는 경우
    · 큰 구멍, 싱크홀 등으로 즉시 사고 위험이 있는 경우
    · 자살·자해를 당장 시도할 것 같은 발언이 반복되는 경우

2) "보통"
  - 즉시 생명위험까지는 아니지만, 조속한 조치가 필요한 물리적/환경적 문제.
  - 예)
    · 가로등이 고장 나 어두워서 위험할 수 있는 골목
    · 도로 파손이 있지만 당장 차량 통행은 가능한 상태
    · 반복되는 소음·악취 등으로 생활에 큰 불편을 주는 경우

3) "경미"
  - 주로 행정·절차문의, 일반 상담, 비교적 가벼운 생활불편.
  - 예)
    · 연금/복지 신청 방법 문의
    · 복지 혜택 자격 상담
    · 일시적인 불편 호소지만 위험 표현이 없는 경우

[안전 보수 규칙]
- "위험·사고·넘어질 것 같다·차가 미끄러질 것 같다" 등
  안전을 직접 언급하면 최소 "보통" 이상으로 올려서 판단해.
- 명백한 감전/추락/충돌 등 가능성이 있으면 "긴급"을 우선 고려해.

--------------------------------------------------
4단계: 모호한 경우 처리

- 카테고리가 애매하면 "기타"로 두고, needs_visit는 false, risk_level은 "경미" 또는 "보통" 중에서
  내용의 심각성에 따라 선택해.
- 다만, 조금이라도 물리적 안전사고가 떠오르는 표현이 있으면
  카테고리를 도로나 시설물/생활민원 중 하나로 잡고,
  needs_visit=true, risk_level을 "보통" 이상으로 설정하는 방향으로 보수적으로 판단해.

--------------------------------------------------
5단계: 출력 형식 (아주 중요)

출력은 반드시 아래 JSON 형식 "하나만" 출력해.
설명, 주석, 자연어 문장은 절대 넣지 마.
코드 블록(```json 등)도 사용하지 마.

{
  "category": "도로" 또는 "시설물" 또는 "연금/복지" 또는 "심리지원" 또는 "생활민원" 또는 "기타" 중 하나의 정확한 문자열,
  "needs_visit": true 또는 false (불리언, 따옴표 없이),
  "risk_level": "긴급" 또는 "보통" 또는 "경미"
}

주의:
- category 값은 반드시 위 6개 중 하나의 정확한 문자열만 사용해.
- needs_visit는 소문자 true/false 불리언으로 출력해. 문자열 "true"/"false"가 아니야.
- risk_level은 "긴급", "보통", "경미" 중 하나의 문자열만 사용해.


category는 반드시 위 목록 중 하나의 '정확한 문자열'만 사용해.
""".strip()  # >>> system 프롬프트 (자주 고치게 될 부분 1)

    user = f"""
민원 내용:
\"\"\"{text}\"\"\"

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
        # LLM이 이상하게 답하면, 규칙 기반 결과로 폴백
        return {
            "category": base_category,
            "needs_visit": False,
            "risk_level": "보통",
        }

    cat = data.get("category") or base_category
    if cat not in MINWON_TYPES:
        cat = base_category

    needs_visit = bool(data.get("needs_visit", False))
    risk_level = data.get("risk_level") or "보통"
    if risk_level not in ("긴급", "보통", "경미"):
        risk_level = "보통"

    return {
        "category": cat,
        "needs_visit": needs_visit,
        "risk_level": risk_level,
    }

def build_fallback_summary(text: str, category: str) -> str:
    """
    요약 LLM이 실패했을 때 사용할 안전한 1차 요약.
    - 카테고리별로 아주 거친 템플릿을 쓰고
    - 그게 안 되면 30자 자르기.
    """
    t = text.strip()

    # 연금/복지: 출생연도 있으면 같이 붙여 주기
    if category == "연금/복지":
        m = re.search(r"(19[0-9]{2}|20[0-2][0-9])년생", t)
        if m:
            return f"{m.group(0)} 연금 수령 시기 문의"
        return "연금 수령 시기/자격 문의"

    # 심리지원
    if category == "심리지원":
        return "정신건강·심리지원 상담 요청"

    # 도로/시설물/생활민원 등 공통 기본값: 30자 자르기
    t_no_nl = t.replace("\n", " ")
    return t_no_nl[:30] + ("..." if len(t_no_nl) > 30 else "")

# -------------------- Summarizer (담당자용 요약 밑재료) --------------------
def summarize_for_staff(text: str, category: str) -> Dict[str, Any]:
    """
    담당자용 30글자 요약 + key_fields 후보 생성.
    JSON 실패 시 안전한 기본값으로 폴백.
    """
    system = (
        "너는 한국 지자체 민원 담당자를 위한 요약기를 돕는 어시스턴트야.\n"
        "주어진 민원을 30글자 이내로 요약하고, 주소/위치, 발생 시각, 위험 정도를 추출해.\n"
        "도로/시설물 민원에서는 특히 '어디인지'가 중요하니, 위치를 최대한 찾아봐.\n"
        "JSON만 출력해. 키: summary_3lines, location, time_info, needs_visit, risk_level."
    )  # >>> 프롬프트 (자주 고칠 부분 2)
    user = f"[카테고리: {category}]\n다음 민원을 요약해줘.\n\n{text}"
    out = call_chat(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=300,
    )

    try:
        data = json.loads(out)
    except Exception:
        # 🔧 LLM JSON 실패 시: 카테고리 기반 30자 요약으로 폴백
        data = {
            "summary_3lines": build_fallback_summary(text, category),
            "location": "",
            "time_info": "",
            "needs_visit": False,
            "risk_level": "보통",
        }

    # 혹시 summary_3lines가 비어 있으면 역시 fallback으로 채움
    data.setdefault("summary_3lines", build_fallback_summary(text, category))
    data.setdefault("location", "")
    data.setdefault("time_info", "")
    data.setdefault("needs_visit", False)
    data.setdefault("risk_level", "보통")


    return data


# -------------------- 국민연금 안내 문구 --------------------
def build_pension_message(text: str) -> str:
    """
    연금/복지 카테고리일 때, 출생연도/나이 단서를 찾아
    노령연금 개시 연령 안내 문구 생성 (있으면).
    """
    m = re.search(r"(19[5-9]\d)년생", text)
    birth_year = None
    if m:
        birth_year = int(m.group(1))

    if birth_year:
        old_age = compute_pension_age(birth_year, "old")
        early_age = compute_pension_age(birth_year, "early")
        return f"{birth_year}년생의 경우 노령연금은 만 {old_age}세, 조기노령연금은 만 {early_age}세부터 가능합니다."
    return ""


# -------------------- handling_type / 접수 방식 결정 --------------------
def decide_handling_from_struct(category: str,
                                needs_visit: bool,
                                risk_level: str,
                                text: str) -> Dict[str, Any]:
    """
    LLM이 정한 category / needs_visit / risk_level을 기반으로
    handling_type, need_call_transfer, need_official_ticket 결정.
    규칙은 최대한 얇게 유지.
    """
    handling_type = "simple_guide"
    need_call_transfer = False
    need_official_ticket = False

    # 심리지원: 상담/전화 연결 우선
    if category == "심리지원":
        handling_type = "contact_only"
        need_call_transfer = True
        need_official_ticket = False

    # 연금/복지: 규정 안내 + 상담 전화 제안
    elif category == "연금/복지":
        handling_type = "simple_guide"
        need_call_transfer = True
        need_official_ticket = False

    # 도로/시설물: 출동 필요하면 official_ticket
    elif category in ("도로", "시설물"):
        if needs_visit:
            handling_type = "official_ticket"
            need_official_ticket = True
        else:
            handling_type = "contact_only"
            need_official_ticket = True  # 서류상 접수만 해도 된다고 가정

    # 생활민원/기타: 기본은 contact_only + 전화 연결
    else:
        handling_type = "contact_only"
        need_call_transfer = True
        need_official_ticket = False

    return {
        "handling_type": handling_type,
        "need_call_transfer": need_call_transfer,
        "need_official_ticket": need_official_ticket,
        "risk_level": risk_level,
        "needs_visit": needs_visit,
    }


# -------------------- user_facing 생성 --------------------
def build_user_facing(category: str,
                      handling: Dict[str, Any],
                      dept: Dict[str, str],
                      text: str) -> Dict[str, str]:
    handling_type = handling["handling_type"]
    need_call_transfer = handling["need_call_transfer"]
    need_official_ticket = handling["need_official_ticket"]

    empathy = "말씀해 주셔서 감사합니다. 많이 불편하셨겠습니다."

    short_title = f"{category} 관련 문의" if category != "기타" else "일반 문의"

    main_message = f"{empathy} 지금 말씀해 주신 내용은 '{category}' 민원으로 보입니다."

    extra_pension = ""
    if category == "연금/복지":
        pm = build_pension_message(text)
        if pm:
            extra_pension = " " + pm

    next_action_guide = ""
    phone_suggestion = ""
    confirm_question = ""

    if handling_type == "simple_guide":
        next_action_guide = (
            f"안내해 드린 내용을 참고하셔서 진행하시면 됩니다.{extra_pension}"
        ).strip()
        if need_call_transfer:
            phone_suggestion = (
                f"개별 상황에 따라 달라질 수 있어 {dept['department_name']}에 전화로 상담을 받으셔도 좋습니다."
            )
        confirm_question = ""

    elif handling_type == "contact_only":
        next_action_guide = (
            f"{dept['department_name']}에서 상황을 듣고 자세히 안내해 드리는 것이 좋겠습니다."
        )
        if need_call_transfer:
            phone_suggestion = (
                f"지금 바로 {dept['contact']}로 전화 연결을 도와드릴까요?"
            )
        confirm_question = "전화 연결을 원하시면 말씀해 주세요."

    else:  # official_ticket
        next_action_guide = (
            "말씀해 주신 내용으로 민원을 정식 접수할 수 있습니다."
        )
        phone_suggestion = (
            f"접수 후 진행 상황은 {dept['department_name']}에서 안내해 드립니다."
        )
        confirm_question = "이 내용으로 민원을 접수해 드릴까요?"

    return {
        "short_title": short_title,
        "main_message": main_message,
        "next_action_guide": next_action_guide,
        "phone_suggestion": phone_suggestion,
        "confirm_question": confirm_question,
    }


# -------------------- staff_payload 생성 --------------------
def extract_citizen_request(text: str) -> str:
    """
    주민이 실제로 '무엇을 해 달라고' 요청하는지 한 문장으로 요약.
    """
    system = (
        "다음 민원 문장에서 주민이 실제로 원하는 조치(요청 사항)를 한 문장으로 요약해줘. "
        "예: '쓰러진 나무를 치워 달라는 요청' 처럼.\n"
        "가능하면 '...해 달라는 요청' 형식으로 끝나게 작성해."
    )  # >>> 프롬프트 (자주 고칠 부분 3)
    out = call_chat(
        [{"role": "system", "content": system},
         {"role": "user", "content": text}],
        model=MODEL,
        temperature=TEMP_GLOBAL,
        max_tokens=80,
    )
    return out or ""


def build_staff_payload(summary_data: Dict[str, Any],
                        category: str,
                        handling: Dict[str, Any],
                        text: str) -> Dict[str, Any]:
    # 🔧 STATE 참조 제거
    location = summary_data.get("location") or ""
    time_info = summary_data.get("time_info", "")
    risk_level = handling["risk_level"]
    needs_visit = bool(summary_data.get("needs_visit") or handling["needs_visit"])

    citizen_request = extract_citizen_request(text)
    raw_keywords = extract_keywords(normalize(text))

    memo_parts = []
    if category == "기타":
        memo_parts.append("카테고리 불명확: 담당자 재분류 필요.")

    # 🔧 주소가 의미 있는 카테고리(도로/시설물/생활민원)에서만 주소 부족을 알림
    if (category in ("도로", "시설물", "생활민원")
            and not summary_data.get("location")):
        memo_parts.append("민원에서 명시적인 주소는 추출되지 않았음.")

    if handling["need_official_ticket"] and not needs_visit:
        memo_parts.append("접수는 필요하나 방문 여부는 담당자 판단 필요.")

    memo_for_staff = " ".join(memo_parts)

    return {
        "summary": summary_data.get("summary_3lines", ""),
        "category": category,
        "location": location,
        "time_info": time_info,
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": citizen_request,
        "raw_keywords": raw_keywords,
        "memo_for_staff": memo_for_staff,
    }



# -------------------- Clarification --------------------
def need_clarification(summary_data: Dict[str, Any],
                       category: str,
                       text: str) -> bool:
    """
    위치/시간 등 핵심 정보 부족 시, 추가 질문을 할지 여부.

    - 도로/시설물인데 location이 완전히 비어 있으면 기본적으로 질문.
    - 다만, LLM이 location을 못 뽑았더라도
      텍스트 안에 '추가 위치 정보' + 동/리/골목/아파트/마을회관/집 앞 등
      위치를 특정할 수 있는 표현이 있으면,
      '완벽하진 않지만 특정 가능'하다고 보고 질문을 멈춘다.
    """
    if category not in ("도로", "시설물"):
        return False

    loc = (summary_data.get("location") or "").strip()
    # LLM이라도 뭔가 위치를 뽑아냈으면 더 이상 안 묻는다.
    if loc:
        return False

    # LLM이 location을 못 뽑았지만, 텍스트 안에 이미 꽤 구체적인 위치 표현이 있으면
    t = text.replace(" ", "")

    # 이미 한 번 이상 "추가 위치 정보:"가 붙은 상황인지 확인
    has_additional_marker = "추가위치정보" in t

    # 동/리/길/골목/아파트/마을회관/집앞/대문 같은 표현이 있는지
    has_location_like_word = bool(
        re.search(r"(동|리|길|로|대로|골목|아파트|마을회관|집앞|대문)", t)
    )

    # 이미 추가 위치 정보를 한 번 이상 받고,
    # 그 안에 구체적인 위치 표현이 있으면 → 더 이상 clarification 하지 않음
    if has_additional_marker and has_location_like_word:
        return False

    # 그 외에는 한 번 더 물어본다.
    return True



def build_clarification_response(text: str,
                                 category: str,
                                 needs_visit: bool,
                                 risk_level: str) -> Dict[str, Any]:
    user_facing = {
        "short_title": "추가 정보 확인",
        "main_message": "죄송하지만, 정확한 위치를 한 번만 더 알려 주시면 좋겠습니다.",
        "next_action_guide": "예를 들어 ○○동 ○○아파트 앞, ○○리 마을회관 앞 골목처럼 말씀해 주세요.",
        "phone_suggestion": "",
        "confirm_question": "",
    }

    staff_payload = {
        "summary": text[:120] + ("..." if len(text) > 120 else ""),
        "category": category,
        "location": "",
        "time_info": "",
        # 🔽 여기서 LLM/규칙이 판단한 값을 그대로 넣어줌
        "risk_level": risk_level,
        "needs_visit": needs_visit,
        "citizen_request": "",
        "raw_keywords": extract_keywords(text),
        "memo_for_staff": (
            "위치 정보 부족으로 추가 질문 필요. "
            "내용상 현장 출동이 필요해 보이는 민원일 수 있음."
            if needs_visit else
            "위치 정보 부족으로 추가 질문 필요."
        ),
    }

    return {
        "stage": "clarification",
        "minwon_type": category,
        "handling_type": "simple_guide",  # 아직은 안내/추가질문 단계
        "need_call_transfer": False,
        "need_official_ticket": False,
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }


# -------------------- 메인 파이프라인 --------------------
def run_pipeline_once(user_text: str,
                      history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    텍스트 한 턴을 받아서 프로젝트 공통 JSON 스키마로 결과를 반환.
    """
    text = user_text.strip()
    if not text:
        return {
            "stage": "classification",
            "minwon_type": "기타",
            "handling_type": "simple_guide",
            "need_call_transfer": False,
            "need_official_ticket": False,
            "user_facing": {
                "short_title": "입력 없음",
                "main_message": "말씀을 잘 못 들었습니다. 다시 한 번 말씀해 주시겠어요?",
                "next_action_guide": "",
                "phone_suggestion": "",
                "confirm_question": "",
            },
            "staff_payload": {
                "summary": "입력된 내용이 없음.",
                "category": "기타",
                "location": "",
                "time_info": "",
                "risk_level": "경미",
                "needs_visit": False,
                "citizen_request": "",
                "raw_keywords": [],
                "memo_for_staff": "STT 결과가 비어 있는 것으로 추정.",
            },
        }

    # >>> 0) 시나리오 규칙 오버라이드 먼저 확인 (안전망)
    scenario_override = detect_scenario_override(text)

    # 1) 규칙 기반 1차 분류
    base_category, needs_visit_rule = rule_first_classify(text)

    # 2) LLM으로 카테고리 + 출동 여부 + 위험도 한 번에 확정
    llm_cf = llm_classify_category_and_fieldwork(text, base_category)
    category = llm_cf["category"]
    needs_visit_llm = llm_cf["needs_visit"]
    risk_level_llm = llm_cf["risk_level"]

    # >>> 시나리오 규칙이 category / needs_visit / risk_level을 강제로 덮어씌움
    if scenario_override is not None:
        if "category" in scenario_override:
            category = scenario_override["category"]
        if "needs_visit" in scenario_override:
            needs_visit_llm = scenario_override["needs_visit"]
        if "risk_level" in scenario_override:
            risk_level_llm = scenario_override["risk_level"]

    # 규칙/LLM 결과를 합쳐서 최종 needs_visit 결정 (보수적 OR)
    final_needs_visit = needs_visit_rule or needs_visit_llm

    # 3) Summarizer
    summary_data = summarize_for_staff(text, category)

    # 4) Clarification 필요 여부
    if need_clarification(summary_data, category, text):
        return build_clarification_response(
            text,
            category,
            needs_visit=final_needs_visit,
            risk_level=risk_level_llm,
        )

    # 5) handling_type / 접수 방식 결정
    handling = decide_handling_from_struct(
        category=category,
        needs_visit=final_needs_visit,
        risk_level=risk_level_llm,
        text=text,
    )

    # >>> 시나리오 규칙이 handling 관련 플래그도 덮어씌움
    if scenario_override is not None:
        if "handling_type" in scenario_override:
            handling["handling_type"] = scenario_override["handling_type"]
        if "need_official_ticket" in scenario_override:
            handling["need_official_ticket"] = scenario_override["need_official_ticket"]
        if "need_call_transfer" in scenario_override:
            handling["need_call_transfer"] = scenario_override["need_call_transfer"]
        # needs_visit는 이미 위에서 반영

    # 6) 부서 정보
    dept = DEPT_MAP.get(category, DEPT_MAP["기타"])

    # 7) 주민용 멘트
    user_facing = build_user_facing(category, handling, dept, text)

    # 8) 담당자용 payload
    staff_payload = build_staff_payload(summary_data, category, handling, text)

    stage = "handoff" if handling["need_official_ticket"] else "guide"

    result = {
        "stage": stage,
        "minwon_type": category,
        "handling_type": handling["handling_type"],
        "need_call_transfer": handling["need_call_transfer"],
        "need_official_ticket": handling["need_official_ticket"],
        "user_facing": user_facing,
        "staff_payload": staff_payload,
    }

    return result


# -------------------- CLI 테스트 --------------------
if __name__ == "__main__":
    print("민원 텍스트 엔진 — 1단계(텍스트 전용) 데모 (exit로 종료)")
    history: List[Dict[str, str]] = []
    while True:
        try:
            text = input("\n민원 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if text.lower() in ("exit", "quit"):
            print("종료합니다.")
            break

        result = run_pipeline_once(text, history)

        uf = result["user_facing"]
        sp = result["staff_payload"]
        print("\n[단계]", result["stage"])
        print("[분류]", result["minwon_type"], "/", result["handling_type"])
        print("[주민용]")
        print(" - 제목:", uf["short_title"])
        print(" - 안내:", uf["main_message"])
        print(" - 다음 행동:", uf["next_action_guide"])
        if uf["phone_suggestion"]:
            print(" - 전화 제안:", uf["phone_suggestion"])
        if uf["confirm_question"]:
            print(" - 확인 질문:", uf["confirm_question"])
        print("[담당자용 요약]")
        print(" - 요약:", sp["summary"])
        print(" - 위치:", sp["location"], "| 시간:", sp["time_info"])
        print(" - 위험도:", sp["risk_level"], "| 방문 필요:", sp["needs_visit"])
        print(" - 요청:", sp["citizen_request"])
        print(" - 키워드:", ", ".join(sp["raw_keywords"]))
        if sp["memo_for_staff"]:
            print(" - 메모:", sp["memo_for_staff"])

        print("FE:" + json.dumps(result, ensure_ascii=False))
        history.append({"role": "user", "content": text})
