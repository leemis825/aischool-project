# brain/staff_report_agent.py
# -*- coding: utf-8 -*-
"""
행정용 민원 요약 보고서(텍스트 버전)를 만드는 레이어.

- 입력: staff_payload (summarizer.summarize_for_staff 결과)
- 출력: 한국 공공 문서 스타일의 보고서 텍스트 (문단/섹션 단위)
"""

from typing import Dict, Any


def build_staff_report_text(staff_payload: Dict[str, Any]) -> str:
    """
    간단한 템플릿 기반 공문 스타일 보고서 텍스트 생성.
    (LLM 안 쓰고 템플릿만으로도 충분히 공공문서 느낌을 낼 수 있음)
    """
    title = "민원 처리 요약 보고서"

    category = staff_payload.get("category", "")
    summary = staff_payload.get("summary", staff_payload.get("summary_3lines", ""))
    location = staff_payload.get("location", "")
    time_info = staff_payload.get("time_info", "")
    risk_level = staff_payload.get("risk_level", "보통")
    needs_visit = staff_payload.get("needs_visit", False)
    citizen_request = staff_payload.get("citizen_request", "")
    memo = staff_payload.get("memo_for_staff", "")
    keywords = staff_payload.get("raw_keywords", [])

    visit_text = "예" if needs_visit else "아니오"
    keywords_text = ", ".join(map(str, keywords)) if keywords else "-"

    lines = [
        f"{title}",
        "",
        "1. 민원 개요",
        f"  가. 민원 유형 : {category}",
        f"  나. 핵심 내용 : {summary}",
        "",
        "2. 발생(의심) 일시 및 장소",
        f"  가. 일시 : {time_info or '-'}",
        f"  나. 장소 : {location or '-'}",
        "",
        "3. 위험도 및 현장 출동 필요 여부",
        f"  가. 위험도 : {risk_level}",
        f"  나. 현장 출동 필요 여부 : {visit_text}",
        "",
        "4. 주민 요청 사항",
        f"  - {citizen_request or '-'}",
        "",
        "5. 담당자 참고 사항",
        f"  - {memo or '-'}",
        "",
        "6. 키워드",
        f"  - {keywords_text}",
    ]

    return "\n".join(lines)
