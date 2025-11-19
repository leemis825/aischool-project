// src/pages/LogsPage.tsx
import { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

interface LogSessionSummary {
  session_id: string;
  first_timestamp?: string;
  last_timestamp?: string;
  event_count: number;
  event_types: string[];
}

interface LogEvent {
  timestamp?: string;
  type?: string;
  input_text?: string;
  used_text?: string;
  source?: string;
  // 그 외 필드들도 있지만, 여기서는 통째로 들고 있다가 JSON 보기용으로 사용
  [key: string]: any;
}

export default function LogsPage() {
  const [sessions, setSessions] = useState<LogSessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1) 세션 목록 불러오기
  useEffect(() => {
    async function fetchSessions() {
      try {
        setLoadingSessions(true);
        const res = await fetch(`${API_BASE}/api/logs/sessions?limit=20`);
        if (!res.ok) {
          throw new Error(`세션 목록 조회 실패: ${res.status}`);
        }
        const data = await res.json();
        setSessions(data.sessions || []);
      } catch (e: any) {
        setError(e.message ?? String(e));
      } finally {
        setLoadingSessions(false);
      }
    }
    fetchSessions();
  }, []);

  // 2) 특정 세션 이벤트 불러오기
  async function fetchSessionDetail(sessionId: string) {
    try {
      setSelectedSessionId(sessionId);
      setLoadingEvents(true);
      setEvents([]);
      const res = await fetch(
        `${API_BASE}/api/logs/${sessionId}?max_events=200`
      );
      if (!res.ok) {
        throw new Error(`세션 상세 조회 실패: ${res.status}`);
      }
      const data = await res.json();
      setEvents(data.events || []);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setLoadingEvents(false);
    }
  }

  return (
    <div style={{ padding: "24px", fontFamily: "system-ui" }}>
      <h1 style={{ fontSize: "28px", marginBottom: "16px" }}>
        백엔드 민원 처리 로그
      </h1>
      <p style={{ marginBottom: "16px", color: "#555" }}>
        왼쪽에서 세션을 선택하면, 오른쪽에 해당 세션의 처리 흐름이 타임라인으로 표시됩니다.
      </p>

      {error && (
        <div
          style={{
            marginBottom: "16px",
            padding: "8px 12px",
            background: "#ffe5e5",
            color: "#b00020",
            borderRadius: "6px",
          }}
        >
          오류: {error}
        </div>
      )}

      <div style={{ display: "flex", gap: "16px" }}>
        {/* 좌측: 세션 목록 */}
        <div style={{ flex: "0 0 420px" }}>
          <h2 style={{ fontSize: "20px", marginBottom: "8px" }}>세션 목록</h2>
          {loadingSessions ? (
            <div>세션 목록 불러오는 중...</div>
          ) : sessions.length === 0 ? (
            <div>아직 기록된 세션이 없습니다.</div>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "13px",
              }}
            >
              <thead>
                <tr style={{ background: "#f4f4f4" }}>
                  <th style={{ border: "1px solid #ddd", padding: "6px" }}>
                    session_id
                  </th>
                  <th style={{ border: "1px solid #ddd", padding: "6px" }}>
                    first
                  </th>
                  <th style={{ border: "1px solid #ddd", padding: "6px" }}>
                    last
                  </th>
                  <th style={{ border: "1px solid #ddd", padding: "6px" }}>
                    count
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr
                    key={s.session_id}
                    onClick={() => fetchSessionDetail(s.session_id)}
                    style={{
                      cursor: "pointer",
                      background:
                        s.session_id === selectedSessionId ? "#e3f2fd" : "white",
                    }}
                  >
                    <td
                      style={{
                        border: "1px solid #ddd",
                        padding: "6px",
                        maxWidth: "170px",
                        whiteSpace: "nowrap",
                        textOverflow: "ellipsis",
                        overflow: "hidden",
                      }}
                      title={s.session_id}
                    >
                      {s.session_id}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "6px" }}>
                      {s.first_timestamp?.slice(11, 19)}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "6px" }}>
                      {s.last_timestamp?.slice(11, 19)}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "6px" }}>
                      {s.event_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 우측: 타임라인 */}
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: "20px", marginBottom: "8px" }}>
            세션 타임라인
          </h2>

          {!selectedSessionId && (
            <div style={{ color: "#777" }}>
              왼쪽에서 세션을 클릭하면 상세 로그가 여기에 표시됩니다.
            </div>
          )}

          {selectedSessionId && loadingEvents && (
            <div>세션 {selectedSessionId} 로그 불러오는 중...</div>
          )}

          {selectedSessionId && !loadingEvents && (
            <div
              style={{
                border: "1px solid #ddd",
                borderRadius: "8px",
                padding: "12px 16px",
                maxHeight: "520px",
                overflowY: "auto",
                background: "#fafafa",
              }}
            >
              {events.length === 0 ? (
                <div>이 세션에는 이벤트가 없습니다.</div>
              ) : (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {events.map((ev, idx) => (
                    <li
                      key={idx}
                      style={{
                        display: "flex",
                        gap: "12px",
                        marginBottom: "12px",
                      }}
                    >
                      <div
                        style={{
                          width: "80px",
                          fontSize: "12px",
                          color: "#666",
                        }}
                      >
                        {ev.timestamp
                          ? ev.timestamp.slice(11, 19)
                          : idx === 0
                          ? "start"
                          : ""}
                      </div>
                      <div
                        style={{
                          flex: 1,
                          background: "white",
                          borderRadius: "8px",
                          border: "1px solid #ddd",
                          padding: "8px 10px",
                          boxShadow:
                            "0 1px 2px rgba(0, 0, 0, 0.04)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            marginBottom: "4px",
                          }}
                        >
                          {ev.type || "event"}
                          {ev.source ? ` · ${ev.source}` : ""}
                        </div>
                        {ev.input_text && (
                          <div
                            style={{
                              fontSize: "13px",
                              marginBottom: "4px",
                            }}
                          >
                            <b>입력:</b> {ev.input_text}
                          </div>
                        )}
                        {ev.used_text && ev.used_text !== ev.input_text && (
                          <div
                            style={{
                              fontSize: "13px",
                              marginBottom: "4px",
                            }}
                          >
                            <b>사용 텍스트:</b> {ev.used_text}
                          </div>
                        )}
                        {ev.engine_result && (
                          <details style={{ fontSize: "12px" }}>
                            <summary>engine_result JSON 보기</summary>
                            <pre
                              style={{
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-all",
                                marginTop: "4px",
                              }}
                            >
                              {JSON.stringify(
                                ev.engine_result,
                                null,
                                2
                              )}
                            </pre>
                          </details>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
