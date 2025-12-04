import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import { useEffect, useRef, useState } from "react";
// 언니 여기예요1🦊🐰
import { sttAndMinwon, type SttMinwonResponse } from "../services/sttService";
import { requestTts } from "../services/ttsService";
import SpeakerImg from "../assets/speaker.png";
import { saveComplaintFromStt } from "../services/complaintService";

export default function ListeningPage() {
  const navigate = useNavigate();

  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sttResult, setSttResult] = useState<string>("");
  const [ttsUrl, setTtsUrl] = useState<string | null>(null); // 🔹 사용자 안내 TTS URL
  const [volume, setVolume] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null); // 🔹 백엔드 세션 ID
  const sessionIdRef = useRef<string | null>(null);

  // 🔹 StrictMode에서 useEffect 두 번 실행되는 것 방지용
  const hasInitRef = useRef(false);

  // 🔹 녹음 관련 ref들
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // 🔹 오디오 비주얼라이저용 ref들
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null); // 현재는 안 쓰지만 남겨둠(확장용)

  // 🔊 볼륨 계산 → 이미지 튕김용
  const trackVolume = () => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const bufferLength = analyser.fftSize;
    const dataArray = new Uint8Array(bufferLength);

    const update = () => {
      animationFrameRef.current = requestAnimationFrame(update);

      analyser.getByteTimeDomainData(dataArray);

      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = (dataArray[i] ?? 128) - 128;
        sum += Math.abs(v);
      }
      const avg = sum / bufferLength; // 0~128
      const normalized = Math.min(avg / 64, 1); // 0~1 범위로 정규화

      setVolume(normalized);
    };

    update();
  };

  const stopVisualizer = () => {
    // 애니메이션 루프 중지
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    // 캔버스 깨끗하게 지우고 배경만 채우기 (현재 UI에는 안 보여도 방어용)
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#4E9948";
    ctx.fillRect(0, 0, width, height);
  };

  // 🔹 녹음 + 볼륨 추적 세팅
  const setupRecorderAndVisualizer = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      mediaStreamRef.current = stream;

      /**
       * 1) MediaRecorder 설정 (녹음용)
       */
      const options: MediaRecorderOptions = {};
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        options.mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/webm")) {
        options.mimeType = "audio/webm";
      }

      const recorder = new MediaRecorder(stream, options);

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          chunksRef.current = [];

          await uploadBlob(blob);
        } catch (err) {
          console.error(err);
          setError("녹음 처리 중 오류가 발생했어요. 다시 시도해 주세요.");
          setIsUploading(false);
        }
      };

      mediaRecorderRef.current = recorder;

      /**
       * 2) AudioContext + Analyser 설정 (볼륨 측정용)
       */
      const audioCtx = new (window.AudioContext ||
        (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048; // 해상도
      source.connect(analyser);
      analyserRef.current = analyser;

      if (analyserRef.current) {
        trackVolume();
      }

      // 🔴 여기서부터 실제 녹음 시작
      recorder.start();
      setIsRecording(true);
      setIsUploading(false);
      setError(null);
    } catch (e) {
      console.error(e);
      setError("마이크 권한을 허용해 주세요.");
    }
  };

  // 🔊 페이지 진입 시: 안내 멘트 → 끝나면 녹음 시작
  useEffect(() => {
    if (hasInitRef.current) return;
    hasInitRef.current = true;

    const speakAndStart = async () => {
      try {
        const text =
          "말씀을 듣고 있어요. 말씀이 끝나면 화면 어디든 눌러 주세요.";
        console.log("[ListeningPage] 안내 TTS:", text);
        const blob = await requestTts(text);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        audio.onended = () => {
          URL.revokeObjectURL(url);
          setupRecorderAndVisualizer();
        };

        audio.onerror = () => {
          URL.revokeObjectURL(url);
          // 재생 실패해도 바로 녹음 시작
          setupRecorderAndVisualizer();
        };

        audio.play();
      } catch (e) {
        console.error("ListeningPage 안내 음성 오류:", e);
        // TTS 호출 자체가 실패해도 녹음은 시작
        setupRecorderAndVisualizer();
      }
    };

    speakAndStart();

    // 언마운트 시 정리
    return () => {
      try {
        if (
          mediaRecorderRef.current &&
          mediaRecorderRef.current.state !== "inactive"
        ) {
          mediaRecorderRef.current.stop();
        }
      } catch {
        // ignore
      }

      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }

      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      if (audioContextRef.current) {
        audioContextRef.current.close();
      }

      stopVisualizer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 언니 여기예요2🦊🐰
  // STT 결과에 대한 안내 멘트(TTS) 재생용
  const callTTS = async (text: string) => {
    try {
      const trimmed = text?.trim();
      if (!trimmed) return;

      // 이전에 만든 오디오 URL이 있으면 정리
      if (ttsUrl) {
        URL.revokeObjectURL(ttsUrl);
      }

      const blob = await requestTts(trimmed);
      const url = URL.createObjectURL(blob);
      setTtsUrl(url);
    } catch (e) {
      console.error(e);
      setError("안내 음성을 불러오는 중 오류가 발생했어요.");
    }
  };

  const uploadBlob = async (blob: Blob) => {
    setError(null);

    try {
      console.log("🎤전송할 오디오 Blob:", blob);
      console.log(
        "👉 uploadBlob 직전 sessionIdRef.current =",
        sessionIdRef.current
      );

      const file = new File([blob], "voice.webm", { type: "audio/webm" });

      // 🔥 이미 세션 ID가 있으면 그걸 계속 사용
      const result: SttMinwonResponse = await sttAndMinwon(
        file,
        sessionIdRef.current
      );
      console.log("🔊 STT+민원 엔진 결과:", result);

      if (result.engine_result) {
        sessionStorage.setItem(
          "last_engine_result",
          JSON.stringify(result.engine_result)
        );
      }

      const finalText = result.text || "(빈 텍스트)";
      setSttResult(finalText);
      setIsUploading(false);

      // ✅ 세션 ID는 "처음 한 번만" 세팅
      if (!sessionIdRef.current && result.session_id) {
        sessionIdRef.current = result.session_id;
        setSessionId(result.session_id);
        console.log("✅ 세션 ID 최초 설정:", result.session_id);
        sessionStorage.setItem("last_session_id", result.session_id);
      } else if (
        sessionIdRef.current &&
        result.session_id &&
        result.session_id !== sessionIdRef.current
      ) {
        console.warn(
          "⚠️ 서버가 다른 session_id를 돌려줬어요. 기존 것을 유지합니다.",
          {
            current: sessionIdRef.current,
            returned: result.session_id,
          }
        );
        // 여기서는 그냥 무시하고 기존 sessionIdRef.current를 계속 사용
      }
      try {
        await saveComplaintFromStt(result, null);
      } catch (err) {
        console.error("민원 저장 중 오류(화면 흐름은 계속 진행):", err);
        // 굳이 사용자에게 에러 표시 안 하고, 흐름만 이어가도 됨
      }

      await callTTS(
        result.user_facing?.main_message ??
          "말씀해 주셔서 감사합니다. 잠시만 기다려 주세요."
      );

      const stage = result.engine_result?.stage;

      if (stage === "clarification") {
        console.log("🔁 clarification 단계 – 다시 녹음 대기");
        await setupRecorderAndVisualizer();
        return;
      }

      navigate("/summary", {
        state: {
          sttText: finalText,
          summary: result.staff_payload?.summary,
          engineResult: result.engine_result,
        },
      });
    } catch (e) {
      console.error(e);
      setError("녹음 처리 중 오류가 발생했어요. 다시 시도해 주세요.");
      setIsUploading(false);
    }
  };

  // 🔹 화면 탭 시: 녹음 종료 + 업로드
  const handleClick = () => {
    if (!isRecording || isUploading) return;
    if (!mediaRecorderRef.current) {
      setError("녹음기가 준비되지 않았어요.");
      return;
    }

    setIsUploading(true);

    try {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      // 🔥 여기서 볼륨 애니메이션 끄기
      stopVisualizer();
    } catch (e) {
      console.error(e);
      setError("녹음을 중단하는 중 오류가 발생했어요.");
      setIsUploading(false);
    }
  };

  return (
    <Layout
      title="민원접수"
      content="말씀을 듣고 있어요"
      topImage="src/assets/top2.png"
      onClick={handleClick}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          marginTop: "25px",
        }}
      >
        <img
          src={SpeakerImg}
          alt="speaker"
          style={{
            width: "230px",
            height: "230px",
            marginTop: "-50px",
            marginBottom: "20px",
            transition: "transform 0.05s linear",
            transform:
              isRecording && !isUploading
                ? `scale(${1 + Math.sin(volume * 10) * 0.2})` // 🔊 녹음 중에만 꿈틀
                : "scale(1)", // 🔇 아니면 고정
          }}
        />

        {error && <p style={{ color: "red" }}>{error}</p>}
        {isRecording && !isUploading && !error && (
          <h2>말씀이 끝나면 화면 어디든 눌러주세요</h2>
        )}
        {isUploading && <h2>인식 중입니다. 잠시만 기다려 주세요...</h2>}
        {sttResult && !isUploading}

        {ttsUrl && !isUploading && (
          <div style={{ marginTop: 16 }}>
            <audio src={ttsUrl} controls autoPlay />
          </div>
        )}
      </div>
    </Layout>
  );
}
