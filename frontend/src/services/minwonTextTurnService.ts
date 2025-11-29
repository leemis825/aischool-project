
import { API_BASE_URL } from "./apiConfig";

/**
 * 민원 카테고리
 * 백엔드에서 정확한 enum을 관리하겠지만,
 * 프론트에서는 일단 string union + fallback string 으로 둬도 됨.
 */
export type MinwonCategory =
  | "도로"
  | "시설물"
  | "연금·복지"
  | "심리지원"
  | "생활민원"
  | "기타"
  | string;

/**
 * 액션 타입 (단순 안내 / 전화 연결 / 공식 민원 접수 등)
 * 백엔드에서 어떤 키를 쓰는지에 따라 맞춰주면 됨.
 */
export type MinwonActionType =
  | "simple_notice"
  | "phone_transfer"
  | "official_report"
  | string;

/**
 * 엔진 결과 타입
 * - category: 민원 카테고리
 * - action_type: 단순 안내 / 전화 연결 / 공식 민원 접수 등
 * - user_facing: 주민 안내용 문구
 * - staff_payload: 담당자용 요약/전달 정보
 * - stage: "normal" | "clarification" 등 (추가 위치 질문 단계 여부)
 * - 기타 필드가 있을 수 있으니 [key: string]: any 도 열어둠
 */
export interface MinwonEngineResult {
  category?: MinwonCategory;
  action_type?: MinwonActionType;
  user_facing?: string;
  staff_payload?: string;
  stage?: string;
  [key: string]: any;
}

/**
 * /api/minwon/text-turn 요청 바디
 * - session_id: 직전 턴에서 받은 세션 ID (첫 턴이면 null 또는 생략)
 * - text: 이번에 들어온 민원 텍스트 (STT 결과 포함)
 */
export interface MinwonTextTurnRequest {
  session_id?: string | null;
  text: string;
}

/**
 * /api/minwon/text-turn 응답 타입
 */
export interface MinwonTextTurnResponse {
  session_id: string;
  used_text: string;
  engine_result: MinwonEngineResult;
}

/**
 * 한 턴의 민원 텍스트를 엔진에 보내고,
 * 카테고리/액션/안내문구/담당자 요약 등을 포함한 결과를 받는 함수
 */
export async function sendMinwonTextTurn(
  payload: MinwonTextTurnRequest
): Promise<MinwonTextTurnResponse> {
  const url = `${API_BASE_URL}/api/minwon/text-turn`;

  console.log("📡 calling text-turn:", url, "payload:", payload);

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    console.error("❌ text-turn error:", res.status, errorText);
    throw new Error(`민원 text-turn 요청 실패: ${res.status}`);
  }

  const data = (await res.json()) as MinwonTextTurnResponse;
  return data;
}
