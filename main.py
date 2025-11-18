# -*- coding: utf-8 -*-
"""
main.py

이 파일은 "간편민원접수" 백엔드 데모의 진입점입니다.

🎯 역할 요약
--------------------------------------
1. 텍스트 전용 모드 (1단계)
   - 사용자가 직접 텍스트로 민원을 입력
   - brain/minwon_engine.py + text_session_state.TextSessionState 사용
   - 👉 하나의 세션 안에서 민원 A / 민원 B 를 구분하고,
       clarification(추가 정보 요청)이 끝나면
       하나의 민원이 마무리되도록 상태를 관리

2. 음성 파일 기반 모드 (2단계 데모)
   - 하나의 오디오 파일을 입력
   - speaker/diarization_pyannote.py 로 화자 분리
   - speaker/stt_whisper.py 로 STT
   - speaker/session_state.py, speaker/speaker.py 로 세션/파이프라인 관리

👉 실제 키오스크에서는
   - 이 main.py를 참고해
   - 마이크 스트리밍 / HTTP 서버 / 웹소켓 등으로 확장하면 됩니다.
"""

import json
from typing import List, Dict, Any

# 텍스트 엔진
from brain.minwon_engine import run_pipeline_once
# 텍스트 세션 상태
from brain.text_session_state import TextSessionState


# =====================================================================
#  모드 1: 텍스트 전용 민원 엔진 데모
# =====================================================================

def run_text_mode():
    """
    콘솔에서 텍스트로 민원을 입력받아
    minwon_engine의 결과를 확인하는 모드입니다.

    ✳ 1단계 멀티턴/Clarification 처리 방식
    ---------------------------------------
    - TextSessionState를 사용해 "민원 A / 민원 B" 개념을 도입
    - 어떤 턴에서 stage == "clarification" 이 나오면
      → 같은 이슈를 open 상태로 유지한 채,
      → 다음 턴 입력을 '추가 위치 정보'로 보고 문장을 합쳐서 엔진에 보낸다.
    - Clarification 이 아닌 결과(guide/handoff 등)가 나오면
      → 해당 이슈를 closed 상태로 바꾸고,
      → 다음 턴은 새로운 이슈(B, C, ...)로 시작한다.
    """
    print("\n[모드 1] 텍스트 민원 엔진 데모 (exit로 종료)")
    history: List[Dict[str, str]] = []
    state = TextSessionState()

    while True:
        try:
            user_raw = input("\n민원 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if user_raw.lower() in ("exit", "quit"):
            print("종료합니다.")
            break

        # ---- 멀티턴 처리: 직전 턴이 clarification이면 문장 합치기 ----
        effective_text = state.build_effective_text(user_raw)

        # ---- 엔진 호출 ----
        result = run_pipeline_once(effective_text, history)

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

        # ---- 히스토리/상태 업데이트 ----
        history.append({"role": "user", "content": effective_text})
        turn = state.register_turn(
            user_raw=user_raw,
            effective_text=effective_text,
            engine_result=result,
        )

        # (선택) 디버깅용: 현재 이슈 상태 출력
        debug = state.debug_issues()
        print("\n[디버그] 현재 이슈 상태:", json.dumps(debug, ensure_ascii=False))


# =====================================================================
#  모드 2: 음성 파일 기반 멀티스피커 민원 처리 데모
# =====================================================================

def run_audio_mode():
    """
    오디오 파일 경로를 입력받아
    - diarization(화자 분리)
    - STT
    - minwon_engine
    까지 한 번에 수행하는 모드입니다.
    """
    print("\n[모드 2] 음성 파일 기반 민원 처리 데모 (exit로 종료)")

    # 🔹 여기서만 import (게으른 import)
    #    → 텍스트 모드(1번)에서는 pyannote/pydub/torch가 없어도 main.py가 잘 실행됨.
    try:
        from speaker.session_state import SessionState
        from speaker.speaker import SpeakerPipeline
    except ImportError as e:
        print(f"[ERROR] 음성 파이프라인 모듈을 불러오지 못했습니다: {e}")
        print("pyannote.audio, torch, torchvision, pydub 등의 설치 여부를 확인해 주세요.")
        return

    state = SessionState()
    pipeline = SpeakerPipeline(state=state)

    while True:
        try:
            path = input("\n오디오 파일 경로 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not path or path.lower() in ("exit", "quit"):
            print("종료합니다.")
            break

        # 세션 시작
        session_id = state.start_session()
        print(f"[INFO] 새 세션 시작: {session_id}")

        results = pipeline.process_audio_file(
            audio_path=path,
            session_id=session_id,
            language="ko",
        )

        if not results:
            print("(처리 결과 없음 또는 오류)")
            continue

        print("\n[세션 처리 결과 타임라인]")
        for item in results:
            spk = item["speaker"]
            turn = item["turn"]
            start = item["start"]
            end = item["end"]
            text = item["text"]
            engine_result = item["engine_result"]

            uf = engine_result["user_facing"]
            sp = engine_result["staff_payload"]

            print(f"\n=== {spk} - turn {turn} ({start:.2f}s ~ {end:.2f}s) ===")
            print("[STT]", text)
            print("[단계]", engine_result["stage"])
            print("[분류]", engine_result["minwon_type"], "/", engine_result["handling_type"])
            print("[주민용 안내]")
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


# =====================================================================
#  메인 진입점
# =====================================================================

def main():
    """
    main.py의 진입점 함수.

    1) 실행 모드 선택
       - 1: 텍스트 민원 엔진
       - 2: 음성 파일 기반 민원 처리
    2) 해당 모드 실행
    """
    print("===== 간편민원접수 백엔드 데모 =====")
    print("1) 텍스트 민원 엔진 (1단계)")
    print("2) 음성 파일 기반 민원 처리 (2단계 데모)")
    print("0) 종료")

    while True:
        mode = input("\n실행 모드를 선택하세요 (1/2/0) > ").strip()
        if mode == "1":
            run_text_mode()
            break
        elif mode == "2":
            run_audio_mode()
            break
        elif mode == "0":
            print("종료합니다.")
            break
        else:
            print("잘못된 입력입니다. 1, 2, 0 중에서 선택해 주세요.")


if __name__ == "__main__":
    main()
