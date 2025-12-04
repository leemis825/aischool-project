// src/services/sttService.ts
import { API_BASE_URL } from "./apiConfig";

/**
 * 백엔드 /stt 응답에서 사용하는 구조들
 */
export interface UserFacing {
  short_title?: string;
  main_message?: string;
  next_action_guide?: string;
  phone_suggestion?: string;
  confirm_question?: string;
}

export interface StaffPayload {
  summary?: string;
  category?: string;
  location?: string;
  time_info?: string;
  risk_level?: string;
  needs_visit?: boolean;
  citizen_request?: string;
  raw_keywords?: string[];
  memo_for_staff?: string;
}

export interface SttMinwonResponse {
  session_id?: string;
  text?: string; // STT 인식 결과
  engine_result?: any; // 민원 엔진 전체 JSON
  user_facing?: UserFacing;
  staff_payload?: StaffPayload;
}

/**
 * 음성 파일 + (선택) session_id 를 보내서
 * STT + 민원엔진 결과를 가져오는 함수
 */
export async function sttAndMinwon(
  audioFile: Blob | File,
  sessionID?: string | null,
  filename: string = "voice.webm"
): Promise<SttMinwonResponse> {
  // 1) 기본 URL + session_id 쿼리스트링
  const baseUrl = `${API_BASE_URL}/stt`;

  const url =
    sessionID && sessionID.trim().length > 0
      ? `${baseUrl}?session_id=${encodeURIComponent(sessionID)}`
      : baseUrl;

  // 2) form-data 구성
  const formData = new FormData();

  // 오디오 파일
  if (audioFile instanceof File) {
    formData.append("audio", audioFile, audioFile.name || filename);
  } else {
    formData.append("audio", audioFile, filename);
  }

  // (선택) session_id 를 form-data 안에도 같이 넣어 준다
  if (sessionID && sessionID.trim().length > 0) {
    console.log("👉 STT 요청에 session_id 포함:", sessionID);
    formData.append("session_id", sessionID);
  } else {
    console.log("👉 STT 요청: session_id 없이 신규 세션 생성");
  }

  // 3) X-Session-ID 헤더도 함께 세팅 (백엔드에서 선택적으로 사용)
  const headers: HeadersInit = {};
  if (sessionID && sessionID.trim().length > 0) {
    headers["X-Session-ID"] = sessionID;
  }

  // 4) 실제 요청
  const res = await fetch(url, {
    method: "POST",
    body: formData,
    headers,
  });

  const raw = await res.text();
  console.log("🔍 /stt raw response:", raw);

  if (!res.ok) {
    // 네트워크/서버 에러를 한 번에 알 수 있게
    throw new Error(`STT+민원 엔진 요청 실패: ${res.status}`);
  }

  // 응답이 항상 JSON 문자열이라고 가정
  const data = JSON.parse(raw) as SttMinwonResponse;
  return data;
}
