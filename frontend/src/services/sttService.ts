// src/services/sttService.ts
import { API_BASE_URL } from "./apiConfig";

export interface UserFacing {
  short_title: string;
  main_message: string;
  next_action_guide: string;
  phone_suggestion: string;
  confirm_question: string;
}

export interface StaffPayload {
  summary: string;
  category: string;
  location: string;
  time_info: string;
  risk_level: string;
  needs_visit: boolean;
  citizen_request: string;
  raw_keywords: string[];
  memo_for_staff: string;
}

export interface EngineResult {
  stage: string;
  minwon_type: string;
  handling_type: string;
  need_call_transfer: boolean;
  need_official_ticket: boolean;
  user_facing: UserFacing;
  staff_payload: StaffPayload;
}

export interface SttMinwonResponse {
  session_id: string | null;
  text: string;
  engine_result: EngineResult;
  user_facing: UserFacing;
  staff_payload: StaffPayload;
}

export async function sttAndMinwon(
  audioFile: File | Blob,
  sessionID?: string | null,
  filename: string = "voice.webm"
): Promise<SttMinwonResponse> {
  // 🔹 session_id를 쿼리스트링으로도 같이 보낼 준비 (선택)
  const baseUrl = `${API_BASE_URL}/stt`;
  
  const url =
    sessionID && sessionID.trim().length > 0
      ? `${baseUrl}?session_id=${encodeURIComponent(sessionID)}`
      : baseUrl;

  const formData = new FormData();

  // 오디오 파일
  if (audioFile instanceof File) {
    formData.append("audio", audioFile, audioFile.name || filename);
  } else {
    formData.append("audio", audioFile, filename);
  }

  // 🔹 1) form-data 안에 session_id 넣기
  if (sessionID && sessionID.trim().length > 0) {
    console.log("👉 STT 요청에 session_id 포함:", sessionID);
    formData.append("session_id", sessionID);
  } else {
    console.log("👉 STT 요청: session_id 없이 새 세션 생성");
  }

  // 🔹 2) 헤더에 X-Session-ID 로도 한 번 더 넣기
  const headers: HeadersInit = {};
  if (sessionID && sessionID.trim().length > 0) {
    headers["X-Session-ID"] = sessionID;
  }

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    headers, // ← 여기 추가
  });

  const raw = await res.text();
  console.log("🔍 /stt raw response:", raw);

  if (!res.ok) {
    throw new Error(`STT+민원 엔진 요청 실패: ${res.status}`);
  }

  const data = JSON.parse(raw) as SttMinwonResponse;
  return data;
}

