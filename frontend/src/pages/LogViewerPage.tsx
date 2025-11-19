// src/pages/LogPage.tsx
import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

type LogSessionSummary = {
  session_id: string;
  first_timestamp?: string | null;
  last_timestamp?: string | null;
  event_count: number;
  event_types: string[];
};

type LogEvent = {
  timestamp?: string;
  type?: string;
  input_text?: string;
  used_text?: string;
  engine_result?: any;
  [key: string]: any;
};

type LogSessionDetail = {
  session_id: string;
  events: LogEvent[];
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("ko-KR");
  } catch {
    return value;
  }
};

const stageLabel: Record<string, string> = {
  classification: "분류",
  guide: "안내",
  handoff: "민원 전달",
  clarification: "추가 질문",
};

export default function LogPage() {
  const [sessions, setSessions] = useState<LogSessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LogSessionDetail | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 페이지 처음 들어왔을 때 세션 목록 불러오기
  useEffect(() => {
    fetchSessions();
  }, []);

  async function fetchSessions() {
    try {
      setError(null);
      setLoadingList(true);
      const res = await fetch(`${API_BASE}/api/logs/sessions?limit=20`);
      if (!res.ok) {
        throw new Error(`세션 목록 조회 실패: ${res.status}`);
      }
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch (e: any) {
      setError(e.message ?? "세션 목록을 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoadingList(false);
    }
  }

  async function fetchDetail(sessionId: string) {
    try {
      setError(null);
      setLoadingDetail(true);
      setSelectedId(sessionId);
      setDetail(null);

      const res = await fetch(
        `${API_BASE}/api/logs/${sessionId}?max_events=200`
      );
      if (!res.ok) {
        throw new Error(`세션 상세 조회 실패: ${res.status}`);
      }
      const data = await res.json();
      setDetail(data);
    } catch (e: any) {
      setError(e.message ?? "세션 로그를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* 왼쪽: 세션 리스트 */}
      <div
        style={{
          width: "40%",
          borderRight: "1px solid #eee",
          padding: "16px",
          overflowY: "auto",
        }}
      >
        <h2 style={{ marginBottom: 8 }}>세션 로그 목록</h2>
        <p style={{ fontSize: 12, color: "#666", marginBottom: 12 }}>
          최근 20개의 세션만 표시됩니다. (stt_turn / stt_multilang_turn 등)
        </p>

        <button
          onClick={fetchSessions}
          style={{
            marginBottom: 12,
            padding: "6px 12px",
            borderRadius: 8,
            border: "1px solid #ddd",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          새로고침
        </button>

        {loadingList && <p>세션 목록을 불러오는 중...</p>}
        {error && (
          <p style={{ color: "red", fontSize: 12, whiteSpace: "pre-wrap" }}>
            {error}
          </p>
        )}

        <div
          style={{
            border: "1px solid #eee",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.5fr 1fr 1fr 0.8fr",
              padding: "8px 12px",
              backgroundColor: "#fafafa",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <span>세션 ID</span>
            <span>첫 이벤트</span>
            <span>마지막 이벤트</span>
            <span>이벤트 수</span>
          </div>

          {sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => fetchDetail(s.session_id)}
              style={{
                width: "100%",
                border: "none",
                borderTop: "1px solid #f1f1f1",
                textAlign: "left",
                padding: "8px 12px",
                backgroundColor:
                  selectedId === s.session_id ? "#fff7d6" : "white",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.5fr 1fr 1fr 0.8fr",
                  gap: 8,
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: "monospace",
                      fontSize: 11,
                      wordBreak: "break-all",
                    }}
                  >
                    {s.session_id}
                  </div>
                  <div style={{ marginTop: 4, color: "#999", fontSize: 11 }}>
                    {s.event_types.join(", ")}
                  </div>
                </div>
                <span>{formatDateTime(s.first_timestamp)}</span>
                <span>{formatDateTime(s.last_timestamp)}</span>
                <span>{s.event_count}</span>
              </div>
            </button>
          ))}

          {sessions.length === 0 && !loadingList && (
            <div style={{ padding: 12, fontSize: 12, color: "#777" }}>
              아직 기록된 세션 로그가 없습니다.
            </div>
          )}
        </div>
      </div>

      {/* 오른쪽: 세션 상세 타임라인 */}
      <div style={{ flex: 1, padding: "16px", overflowY: "auto" }}>
        <h2 style={{ marginBottom: 8 }}>세션 상세</h2>
        {selectedId ? (
          <p style={{ fontSize: 12, color: "#555", marginBottom: 12 }}>
            선택된 세션 ID:{" "}
            <span style={{ fontFamily: "monospace" }}>{selectedId}</span>
          </p>
        ) : (
          <p style={{ fontSize: 12, color: "#777" }}>
            왼쪽에서 세션을 하나 선택하면 상세 이벤트가 여기 표시됩니다.
          </p>
        )}

        {loadingDetail && <p>세션 로그를 불러오는 중...</p>}

        {detail && (
          <div style={{ marginTop: 8 }}>
            {detail.events.map((ev, idx) => {
              const ts = formatDateTime(ev.timestamp);
              const stage = ev.engine_result?.stage;
              const stageText =
                stage && stageLabel[stage]
                  ? `${stageLabel[stage]} (${stage})`
                  : stage || "-";

              const shortInput =
                ev.input_text || ev.used_text || ev.engine_result?.input || "";

              return (
                <div
                  key={idx}
                  style={{
                    borderLeft: "3px solid #ffbf00",
                    paddingLeft: 10,
                    marginBottom: 10,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: "#666",
                    }}
                  >
                    <span>{ts}</span>
                    <span>{ev.type}</span>
                  </div>
                  {shortInput && (
                    <div
                      style={{
                        marginTop: 4,
                        fontSize: 13,
                        fontWeight: 500,
                      }}
                    >
                      {shortInput.length > 80
                        ? shortInput.slice(0, 80) + "..."
                        : shortInput}
                    </div>
                  )}
                  {stage && (
                    <div
                      style={{
                        marginTop: 2,
                        fontSize: 11,
                        color: "#444",
                      }}
                    >
                      처리 단계: {stageText}
                    </div>
                  )}

                  {/* 전체 JSON이 필요하면 아래 주석 풀어서 사용 */}
                  {/* <pre style={{ marginTop: 6, fontSize: 10, background: "#fafafa", padding: 6, borderRadius: 4 }}>
                    {JSON.stringify(ev, null, 2)}
                  </pre> */}
                </div>
              );
            })}

            {detail.events.length === 0 && (
              <p style={{ fontSize: 12, color: "#777" }}>
                이 세션에는 이벤트가 없습니다.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
