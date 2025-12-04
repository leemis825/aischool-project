// src/services/complaintService.ts
import { API_BASE_URL } from "./apiConfig";
import type { SttMinwonResponse } from "./sttService";

export async function saveComplaintFromStt(
  result: SttMinwonResponse,
  userId: number | null = null
): Promise<void> {
  const payload = {
    // 🔹 ComplaintCreate 스키마랑 맞춰서 만들기
    user_id: userId,
    session_id: result.session_id ?? "",

    title: result.user_facing.short_title,
    raw_text: result.text,
    category: result.engine_result.minwon_type,

    minwon_type: result.engine_result.minwon_type,
    handling_type: result.engine_result.handling_type,
    risk_level: result.staff_payload.risk_level,
    needs_visit: result.staff_payload.needs_visit,
    citizen_request: result.staff_payload.citizen_request,
    summary: result.staff_payload.summary,
    location: result.staff_payload.location || null,

    // 🔹 이번 턴 대화 내용 → ComplaintMessage 로 저장될 부분
    stt_text: result.text,
    bot_answer: result.user_facing.main_message, // 또는 tts_result 써도 됨
    audio_url: null,
    tts_audio_url: null,
  };

  const res = await fetch(`${API_BASE_URL}/complaints/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    console.error("❌ 민원 저장 실패:", res.status, text);
    throw new Error("민원 저장 실패");
  }

  const data = await res.json();
  console.log("✅ 민원 저장 성공:", data);
}

export async function updateComplaintPhone(
  sessionId: string,
  phoneNumber: string
): Promise<void> {
  const payload = {
    session_id: sessionId,
    phone_number: phoneNumber,
  };

  const res = await fetch(`${API_BASE_URL}/complaints/set-phone`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  console.log("📡 /complaints/set-phone response:", text);

  if (!res.ok) {
    throw new Error(`전화번호 저장 실패: ${res.status} ${text}`);
  }
}
