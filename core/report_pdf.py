# core/report_pdf.py
# -*- coding: utf-8 -*-

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from typing import Dict, Any
from brain.staff_report_agent import build_staff_report_text


def build_staff_report_pdf(staff_payload: Dict[str, Any], file_path: str) -> str:
    """
    staff_payload를 받아 한국 공공 문서 느낌의 PDF를 생성한다.
    file_path 에 저장하고, 최종 경로를 반환.
    """
    text = build_staff_report_text(staff_payload)

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # 상단 여백/타이틀
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, height - 25 * mm, "민원 처리 요약 보고서")

    # 본문
    c.setFont("Helvetica", 11)

    # 줄 단위로 나누어 그리기
    y = height - 40 * mm
    for line in text.split("\n"):
        if y < 20 * mm:  # 페이지 바닥이면 새 페이지
            c.showPage()
            c.setFont("Helvetica", 11)
            y = height - 25 * mm
        c.drawString(20 * mm, y, line)
        y -= 6 * mm

    c.showPage()
    c.save()
    return file_path
