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
  session_id: string;
  text: string;
  engine_result: EngineResult;
  user_facing: UserFacing;
  staff_payload: StaffPayload;
}

export async function sttAndMinwon(
  audioFile: File | Blob,
  filename: string = "voice.webm"
): Promise<SttMinwonResponse> {
  const url = `${API_BASE_URL}/stt`;

  const formData = new FormData();
  formData.append("audio", audioFile, (audioFile as File).name ?? filename);

  console.log("📡 calling STT+Minwon:", url);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  const raw = await res.text();
  console.log("🔍 /stt raw response:", raw);

  if (!res.ok) {
    throw new Error(`STT+민원 엔진 요청 실패: ${res.status}`);
  }

  const data = JSON.parse(raw) as SttMinwonResponse;
  return data;
}
