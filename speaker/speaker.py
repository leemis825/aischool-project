# -*- coding: utf-8 -*-
"""
speaker.py

이 모듈은 "한 번의 녹음 파일"을 기준으로

1) pyannote.audio 로 화자 구분 (diarization)
2) 각 화자 구간별로 오디오를 잘라서 STT(Whisper) 수행
3) minwon_engine 텍스트 엔진에 전달하여 민원 분류/요약 수행
4) SessionState 에 화자별 상태를 갱신

까지를 한 번에 처리하는 "오디오 → 텍스트 → 민원엔진" 상위 레이어입니다.

🎯 역할 요약
--------------------------------------
- input : audio_path (녹음 파일), session_id
- process:
    diarization → segment 단위 STT → 민원 엔진 호출
- output:
    [
      {
        "speaker": "SPEAKER_00",
        "turn": 1,
        "start": 0.0,
        "end": 3.21,
        "text": "...",
        "engine_result": { ... }
      },
      ...
    ]

👉 이 모듈은 "파일 단위"로만 생각합니다.
   실제 마이크 스트리밍/실시간 처리는 main.py 또는 별도 레이어에서 구현합니다.
"""

import io
from typing import List, Dict, Any

# 오디오 자르기를 위한 라이브러리
# pip install pydub
# 그리고 ffmpeg 가 시스템에 설치되어 있어야 합니다.
from pydub import AudioSegment

from speaker.diarization_pyannote import PyannoteDiarizer
from speaker.stt_whisper import transcribe_bytes
from speaker.session_state import SessionState
from brain.minwon_engine import run_pipeline_once


class SpeakerPipeline:
    """
    하나의 녹음 파일을 기준으로
    - 화자 분리
    - STT
    - 민원 엔진 호출
    을 모두 수행하는 헬퍼 클래스입니다.
    """

    def __init__(self,
                 state: SessionState,
                 diarizer: PyannoteDiarizer | None = None):
        """
        :param state: SessionState 인스턴스 (세션/화자 상태 관리)
        :param diarizer: PyannoteDiarizer 인스턴스 (없으면 내부에서 생성)
        """
        self.state = state
        self.diarizer = diarizer or PyannoteDiarizer()

    # ------------------------------------------------------------------
    # 내부 유틸: 오디오 구간 자르기
    # ------------------------------------------------------------------

    @staticmethod
    def _slice_audio(audio: AudioSegment,
                     start_sec: float,
                     end_sec: float) -> bytes:
        """
        AudioSegment 객체에서 [start_sec, end_sec] 구간을 잘라
        WAV 포맷의 bytes 로 반환합니다.

        Whisper STT에 전달하기 위해 BytesIO에 export하는 용도입니다.
        """
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        segment = audio[start_ms:end_ms]

        buf = io.BytesIO()
        # Whisper가 안정적으로 읽을 수 있도록 WAV 형태로 export
        segment.export(buf, format="wav")
        buf.seek(0)
        return buf.read()

    # ------------------------------------------------------------------
    # 메인: 파일 하나 전체 처리
    # ------------------------------------------------------------------

    def process_audio_file(self,
                           audio_path: str,
                           session_id: str,
                           language: str = "ko") -> List[Dict[str, Any]]:
        """
        하나의 음성 파일을 전체 처리합니다.

        1) diarization 으로 화자/구간 리스트 얻기
        2) 파일을 AudioSegment로 로드
        3) 각 구간마다:
            - 오디오 자르기
            - STT 수행
            - SessionState에서 turn/history 조회
            - (화자별 TextSessionState에서 effective_text 생성)
            - minwon_engine.run_pipeline_once 호출
            - TextSessionState.register_turn + SessionState.update_state 반영
        4) 전체 타임라인 리스트 반환

        :param audio_path: 입력 음성 파일 경로
        :param session_id: SessionState에서 관리하는 세션 ID
        :param language: STT 언어 코드 (기본값 'ko' = 한국어)
        :return: segment별 처리 결과 리스트
        """
        # 1) 화자 구분
        segments = self.diarizer.diarize_file(audio_path)
        if not segments:
            print("[WARN] process_audio_file: diarization 결과가 비어 있습니다.")
            return []

        # 2) 오디오 파일 로드
        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as e:
            print(f"[WARN] 오디오 파일 로드 실패: {e}")
            return []

        results: List[Dict[str, Any]] = []

        # 3) 각 segment 처리
        for seg in segments:
            speaker_id = seg["speaker"]
            start = float(seg["start"])
            end = float(seg["end"])

            # 3-1) 오디오 자르기
            audio_bytes = self._slice_audio(audio, start, end)

            # 3-2) STT
            text = transcribe_bytes(audio_bytes, language=language, file_name="segment.wav")
            if not text.strip():
                # STT가 비어 있으면 이 구간은 스킵 (노이즈/무음 등)
                print(f"[INFO] STT 결과 비어 있음: {speaker_id} {start:.2f}~{end:.2f}")
                continue

            # 3-3) SessionState에서 TextSessionState / turn / history 가져오기
            text_state = self.state.get_text_state(session_id, speaker_id)
            # 텍스트 모드와 동일하게: 직전 턴이 clarification이면 문장 합치기
            effective_text = text_state.build_effective_text(text)

            turn = self.state.next_turn(session_id, speaker_id)
            history = self.state.get_history(session_id, speaker_id)

            # 3-4) 민원 텍스트 엔진 호출 (effective_text 기준)
            engine_result = run_pipeline_once(effective_text, history)

            # 3-5) TextSessionState 멀티턴 상태 갱신 (이슈 A/B/C, clarification 등)
            text_state.register_turn(
                user_raw=text,
                effective_text=effective_text,
                engine_result=engine_result,
            )

            # 3-6) SessionState 갱신 (화자별 history/last_location/last_category)
            self.state.update_state(
                session_id=session_id,
                speaker_id=speaker_id,
                engine_result=engine_result,
                user_text=text,
            )

            # 3-7) 이 segment에 대한 결과 기록
            results.append({
                "speaker": speaker_id,
                "turn": turn,
                "start": start,
                "end": end,
                "text": text,
                "effective_text": effective_text,
                "engine_result": engine_result,
            })

        return results


# ----------------------------------------------------------------------
# 간단 CLI 테스트용 (파일 하나 처리 흐름 확인)
# ----------------------------------------------------------------------

if __name__ == "__main__":
    """
    python -m speaker.speaker 처럼 실행하면
    - session_state 생성
    - PyannoteDiarizer + SpeakerPipeline 생성
    - 사용자에게 오디오 파일 경로를 입력 받아
      전체 처리 결과를 출력합니다.
    """
    from speaker.session_state import SessionState

    print("SpeakerPipeline 테스트 모드입니다.")
    print("오디오 파일 하나를 화자/민원 단위로 처리합니다. (종료: 빈 줄)")

    state = SessionState()
    pipeline = SpeakerPipeline(state=state)

    while True:
        path = input("\n오디오 파일 경로 > ").strip()
        if not path:
            print("종료합니다.")
            break

        session_id = state.start_session()
        print(f"[INFO] 새 세션 시작: {session_id}")

        results = pipeline.process_audio_file(path, session_id=session_id, language="ko")

        if not results:
            print("(결과 없음 또는 오류)")
            continue

        print("\n[처리 결과 타임라인]")
        for item in results:
            spk = item["speaker"]
            turn = item["turn"]
            start = item["start"]
            end = item["end"]
            text = item["text"]
            print(f"\n=== {spk} - turn {turn} ({start:.2f}s ~ {end:.2f}s) ===")
            print("[STT]", text)
            print("[엔진 결과] stage:", item["engine_result"]["stage"],
                  "| type:", item["engine_result"]["minwon_type"],
                  "| handling:", item["engine_result"]["handling_type"])
