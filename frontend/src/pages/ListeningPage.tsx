import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout.js";
import { useEffect, useRef, useState } from "react";
// 언니 여기예요1🦊🐰
import { sttAndMinwon } from "../services/sttService";
import { requestTts } from "../services/ttsService";
import SpeakerImg from "../assets/speaker.png";

export default function ListeningPage() {
  const navigate = useNavigate();

  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sttResult, setSttResult] = useState<string>("");
  const [ttsUrl, setTtsUrl] = useState<string | null>(null); // 🔹 TTS 오디오 URL
  const [volume, setVolume] = useState(0);
  // 🔹 녹음 관련 ref들
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // 🔹 오디오 비주얼라이저용 ref들
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
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
         * 2) AudioContext + Analyser 설정 (파형 그리기용)
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

        // 자동 녹음 시작
        recorder.start();
        setIsRecording(true);
      } catch (e) {
        console.error(e);
        setError("마이크 권한을 허용해 주세요.");
      }
    };

    setupRecorderAndVisualizer();

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
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

    // 캔버스 깨끗하게 지우고 배경만 채우기
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#4E9948";
    ctx.fillRect(0, 0, width, height);
  };

  // 언니 여기예요2🦊🐰
  const callTTS = async (text: string) => {
    try {
      const trimmed = text?.trim();
      if (!trimmed) return;

      // 이전에 만든 오디오 URL이 있으면 정리
      if (ttsUrl) {
        URL.revokeObjectURL(ttsUrl);
      }

      const blob = await requestTts(trimmed); // ← 서비스 함수 호출
      const url = URL.createObjectURL(blob);
      setTtsUrl(url);
    } catch (e) {
      console.error(e);
      setError("안내 음성을 불러오는 중 오류가 발생했어요.");
    }
  };
  // 🔹 Blob을 받아서 /stt 로 업로드
  const uploadBlob = async (blob: Blob) => {
    setError(null);

    try {
      console.log("🎤전송할 오디오 Blob:", blob);
      console.log("크기(bytes):", blob.size);
      console.log("타입:", blob.type);
      const file = new File([blob], "voice.webm", { type: "audio/webm" });
      console.log("🎤생성된 File:", file);

      // 언니 여기예요3🦊🐰
      const resultText = await sttAndMinwon(file);
      console.log("🔊 STT+민원 엔진 결과:", resultText);

      const finalText = resultText || "(빈 텍스트)";
      setSttResult(finalText);
      setIsUploading(false);

      // 🔹 STT 결과를 음성으로도 안내
      await callTTS(
        finalText || "민원이 접수되었습니다. 잠시만 기다려 주세요."
      );

      // 나중에 summary 페이지로 이동하려면 여기에서 navigate
      // navigate("/summary", { state: { sttText: finalText } });
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
    navigate("/summary");

    try {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      // 🔥 여기서 파형 끄기
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
      content="민원을 듣고 있어요"
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
            marginBottom: "20px",
            transition: "transform 0.05s linear",
            transform: `scale(${1 + Math.sin(volume * 10) * 0.2})`,

            // volume=0 → scale(1)
            // volume=1 → scale(1.6) 정도
          }}
        />

        {error && <p style={{ color: "red" }}>{error}</p>}
        {isRecording && !isUploading && !error && (
          <h2>말씀이 끝나면 화면을 눌러주세요</h2>
        )}
        {isUploading && <p>인식 중입니다. 잠시만 기다려 주세요...</p>}
        {sttResult && !isUploading && (
          <>
            <p style={{ fontWeight: "bold", marginBottom: 8 }}>인식된 텍스트</p>
            <p>{sttResult}</p>
          </>
        )}

        {ttsUrl && !isUploading && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>안내 음성</p>
            <audio src={ttsUrl} controls autoPlay />
          </div>
        )}
      </div>
    </Layout>
  );
}
