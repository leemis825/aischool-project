// src/services/complaintService.ts
import { API_BASE_URL } from "./apiConfig";
import type { SttMinwonResponse } from "./sttService";

/**
 * STT + 민원 엔진 결과를 백엔드 /complaints/create 로 전달
 * - ComplaintCreate Pydantic 스키마와 필드를 맞춤
 */
export async function saveComplaintFromStt(
  result: SttMinwonResponse,
  userId: number | null = null
): Promise<void> {
  if (!result.session_id) {
    console.warn("[saveComplaintFromStt] session_id가 없습니다. 저장을 건너뜁니다.");
    return;
  }

  const payload = {
    // 🔹 ComplaintCreate 스키마와 1:1 매핑
    user_id: userId,
    session_id: result.session_id,

    title: result.user_facing?.short_title ?? null,
    raw_text: result.text ?? null,

    // category가 따로 있으면 우선 사용, 없으면 minwon_type 사용
    category:
      result.staff_payload?.category ??
      result.engine_result?.minwon_type ??
      null,

    minwon_type: result.engine_result?.minwon_type ?? null,
    handling_type: result.engine_result?.handling_type ?? null,
    risk_level: result.staff_payload?.risk_level ?? null,
    needs_visit: result.staff_payload?.needs_visit ?? null,
    citizen_request: result.staff_payload?.citizen_request ?? null,
    summary: result.staff_payload?.summary ?? null,
    location: result.staff_payload?.location ?? null,

    // 🔹 전체 엔진 결과를 그대로 보관하고 싶으면 여기에
    engine_result: result.engine_result ?? null,
  };

  const res = await fetch(`${API_BASE_URL}/complaints/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const text = await res.text().catch(() => "");
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // JSON 파싱 실패해도 치명적이지 않으니 무시
  }

  if (!res.ok) {
    console.error("❌ 민원 저장 실패:", res.status, text);
    throw new Error(`민원 저장 실패: ${res.status}`);
  }

  console.log("✅ 민원 저장 응답:", data);
}

/**
 * 요약 페이지에서 전화번호 입력 후 백엔드에 저장
 */
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
