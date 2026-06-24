"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play, Square } from "lucide-react";
import type { SttRealtimeStatus } from "@/lib/useSttRealtime";

interface Props {
  status: SttRealtimeStatus;
  isPaused: boolean;
  analyserRef: React.RefObject<AnalyserNode | null>;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

function WaveformCanvas({
  analyserRef,
  isPaused,
  active,
}: {
  analyserRef: React.RefObject<AnalyserNode | null>;
  isPaused: boolean;
  active: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const BAR_COUNT = 36;
    const BRAND = "#3B7BF6";
    const MUTED = "#cbd5e1";

    const draw = () => {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const analyser = analyserRef.current;
      if (active && analyser && !isPaused) {
        // 녹음 중: 마이크 음량 기반 ECG 심박 애니메이션
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);
        const avgLevel = data.reduce((s, v) => s + v, 0) / data.length / 255;
        const amp = 0.3 + avgLevel * 0.7; // 음량에 따라 진폭 조절

        const t = Date.now() / 1000;
        const period = 1.4;
        const phase = (t % period) / period;

        ctx.strokeStyle = BRAND;
        ctx.lineWidth = 1.5;
        ctx.lineJoin = "round";
        ctx.beginPath();

        for (let x = 0; x <= W; x++) {
          const p = (1 - x / W + phase + 1) % 1;
          let dy = 0;
          if (p < 0.05)                   dy = -Math.sin((p / 0.05) * Math.PI) * H * 0.09 * amp;
          else if (p >= 0.12 && p < 0.15) dy =  H * 0.05 * amp;
          else if (p >= 0.15 && p < 0.20) dy = -Math.sin(((p - 0.15) / 0.05) * Math.PI) * H * 0.40 * amp;
          else if (p >= 0.20 && p < 0.23) dy =  H * 0.07 * amp;
          else if (p >= 0.28 && p < 0.45) dy = -Math.sin(((p - 0.28) / 0.17) * Math.PI) * H * 0.13 * amp;

          const y = H / 2 + dy;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else {
        // 일시정지 / 연결 중: 정적 수평선
        ctx.fillStyle = MUTED;
        ctx.fillRect(0, H / 2 - 1, W, 2);
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserRef, isPaused, active]);

  return (
    <canvas
      ref={canvasRef}
      width={260}
      height={64}
      className="w-full rounded-lg"
    />
  );
}

function useElapsedTime(running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);
  const pausedAtRef = useRef<number>(0);

  useEffect(() => {
    if (!running) {
      setElapsed(0);
      startRef.current = null;
      pausedAtRef.current = 0;
      return;
    }
    startRef.current = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - (startRef.current ?? Date.now())) / 1000));
    }, 500);
    return () => clearInterval(id);
  }, [running]);

  return elapsed;
}

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function SttRecordingModal({
  status,
  isPaused,
  analyserRef,
  onPause,
  onResume,
  onStop,
}: Props) {
  const isRecording = status === "recording";
  const isConnecting = status === "connecting";
  const isStopping = status === "stopping";
  const elapsed = useElapsedTime(isRecording);

  if (!isConnecting && !isRecording && !isStopping) return null;

  const statusLabel = isConnecting
    ? "연결 중..."
    : isStopping
      ? "분석 중..."
      : isPaused
        ? "일시정지됨"
        : "녹음 중";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-[300px] rounded-2xl bg-white p-5 shadow-2xl ring-1 ring-black/5">
        {/* 헤더 */}
        <div className="mb-4 flex items-center justify-between">
          <p className="text-[14px] font-extrabold text-foreground">실시간 녹음</p>
          <span
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
              isConnecting || isStopping
                ? "bg-muted text-muted-foreground"
                : isPaused
                  ? "bg-yellow-50 text-yellow-600"
                  : "bg-red-50 text-red-500"
            }`}
          >
            {!isConnecting && !isStopping && (
              <span
                className={`size-1.5 rounded-full ${
                  isPaused ? "bg-yellow-400" : "animate-pulse bg-red-500"
                }`}
              />
            )}
            {statusLabel}
          </span>
        </div>

        {/* 파형 */}
        <div className="mb-3 rounded-xl bg-slate-50 p-3">
          <WaveformCanvas
            analyserRef={analyserRef}
            isPaused={isPaused}
            active={isRecording}
          />
        </div>

        {/* 타이머 */}
        <p className="mb-4 text-center text-[28px] font-extrabold tabular-nums text-foreground">
          {formatTime(elapsed)}
        </p>

        {/* 컨트롤 */}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!isRecording}
            onClick={isPaused ? onResume : onPause}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-muted py-2.5 text-[13px] font-bold text-foreground transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isPaused ? (
              <>
                <Play className="size-4" />
                재개
              </>
            ) : (
              <>
                <Pause className="size-4" />
                일시정지
              </>
            )}
          </button>
          <button
            type="button"
            disabled={!isRecording}
            onClick={onStop}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-brand py-2.5 text-[13px] font-bold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Square className="size-4 fill-white" />
            종료
          </button>
        </div>
      </div>
    </div>
  );
}
