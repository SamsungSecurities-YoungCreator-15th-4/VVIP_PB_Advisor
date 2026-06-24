import { useCallback, useRef, useState } from "react";
import { useDashboardStore } from "@/lib/store";
import type { ConsultMessage } from "@/lib/mockData";
import type {
  ConsultationResponse,
  IpsJson,
  TranscriptItem,
} from "@/lib/api/types";
import type { IpsPatch } from "@/lib/api/stt";

export type SttRealtimeStatus =
  | "idle"
  | "connecting"
  | "recording"
  | "stopping"
  | "done"
  | "error";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const WS_ENDPOINT =
  API_BASE.replace(/^http:/, "ws:").replace(/^https:/, "wss:") +
  "/consultations/stt/realtime";

// ── 매핑 헬퍼 (stt.ts 와 동일 로직) ──────────────────────────────

function mapTranscriptItems(items: TranscriptItem[]): ConsultMessage[] {
  return items.map((it) => ({
    speaker: it.speaker_role === "PB" ? "PB" : "고객",
    text: it.text ?? "",
    time: it.utterance_time ?? "",
  }));
}

function toNumber(v: number | string | null): number | undefined {
  if (v === null) return undefined;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : undefined;
}

function mapIpsJson(ips: IpsJson | null | undefined): IpsPatch {
  const p: IpsPatch = {};
  if (!ips) return p;
  if (ips.Goal != null) p.goal = ips.Goal;
  const ret = toNumber(ips.Return);
  if (ret !== undefined) p.returnPct = ret;
  if (ips.Risk === "안정형" || ips.Risk === "균형형" || ips.Risk === "공격형")
    p.risk = ips.Risk;
  const time = toNumber(ips.Time);
  if (time !== undefined) p.timeYears = time;
  if (ips.Tax != null) p.tax = ips.Tax;
  if (
    ips.Liquidity === "낮음" ||
    ips.Liquidity === "중간" ||
    ips.Liquidity === "높음"
  )
    p.liquidity = ips.Liquidity;
  if (ips.Legal != null) p.legal = ips.Legal;
  if (ips.Unique != null) p.unique = ips.Unique;
  return p;
}

interface PartialItem {
  sequence: number;
  speaker_label: string;
  speaker_role: string | null;
  text: string;
}

// 실시간 부분 전사용 화자 매핑 — 첫 등장 화자=고객, 두 번째=PB (휴리스틱)
function mapPartialItem(
  item: PartialItem,
  speakerMap: Map<string, "PB" | "고객">,
): ConsultMessage {
  let role = speakerMap.get(item.speaker_label);
  if (!role) {
    role = speakerMap.size === 0 ? "고객" : "PB";
    speakerMap.set(item.speaker_label, role);
  }
  return { speaker: role, text: item.text, time: "" };
}

// ── 훅 본체 ──────────────────────────────────────────────────────

export function useSttRealtime() {
  const [status, setStatus] = useState<SttRealtimeStatus>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const isActiveRef = useRef(false);
  const partialsRef = useRef<PartialItem[]>([]);
  const speakerMapRef = useRef<Map<string, "PB" | "고객">>(new Map());

  const { setTranscript, setConsultationId, setIps } = useDashboardStore();

  const cleanup = useCallback(() => {
    isActiveRef.current = false;
    workletRef.current?.disconnect();
    workletRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState < WebSocket.CLOSING) ws.close();
    partialsRef.current = [];
    speakerMapRef.current = new Map();
  }, []);

  const start = useCallback(
    async (clientId: string) => {
      if (status !== "idle" && status !== "done" && status !== "error") return;
      setStatus("connecting");
      setErrorMsg(null);
      isActiveRef.current = true;

      try {
        // 1) 마이크 권한 요청
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: false,
        });
        streamRef.current = stream;

        // 2) AudioContext + WorkletNode 준비
        const audioCtx = new AudioContext();
        audioCtxRef.current = audioCtx;
        await audioCtx.audioWorklet.addModule("/pcm-processor.js");
        const workletNode = new AudioWorkletNode(audioCtx, "pcm-processor", {
          processorOptions: { targetSampleRate: 16000 },
        });
        workletRef.current = workletNode;

        // 3) WebSocket 연결
        const ws = new WebSocket(WS_ENDPOINT);
        ws.binaryType = "arraybuffer";
        wsRef.current = ws;

        ws.onopen = () => {
          ws.send(
            JSON.stringify({
              client_id: clientId,
              sample_rate: 16000,
              bits_per_sample: 16,
              channels: 1,
            }),
          );
        };

        ws.onmessage = (evt) => {
          if (typeof evt.data !== "string") return;
          let msg: Record<string, unknown>;
          try {
            msg = JSON.parse(evt.data) as Record<string, unknown>;
          } catch {
            return;
          }

          const event = msg.event as string;

          if (event === "started") {
            // 4) 오디오 그래프 연결 — WorkletNode가 PCM 청크를 WS로 전달
            const source = audioCtx.createMediaStreamSource(stream);
            workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(e.data);
              }
            };
            source.connect(workletNode);
            setStatus("recording");
          } else if (event === "partial_transcript") {
            const item = msg.transcript as PartialItem;
            partialsRef.current = [...partialsRef.current, item];
            const mapped = partialsRef.current.map((it) =>
              mapPartialItem(it, speakerMapRef.current),
            );
            setTranscript(mapped, "live");
          } else if (event === "completed") {
            const consultation = msg.consultation as ConsultationResponse;
            setConsultationId(consultation.consultation_id);
            setTranscript(
              mapTranscriptItems(consultation.transcript_json ?? []),
              "live",
            );
            const patch = mapIpsJson(consultation.ips_json);
            if (Object.keys(patch).length > 0) setIps(patch);
            setStatus("done");
            cleanup();
          } else if (event === "error") {
            const detail =
              (msg.detail as string) ?? "실시간 STT 오류가 발생했습니다.";
            setErrorMsg(detail);
            setStatus("error");
            cleanup();
          }
        };

        ws.onerror = () => {
          if (!isActiveRef.current) return;
          const msg = "WebSocket 연결 오류가 발생했습니다.";
          setErrorMsg(msg);
          setStatus("error");
          cleanup();
        };

        ws.onclose = (evt) => {
          if (!isActiveRef.current) return;
          // 정상 종료(1000/1001)는 completed 핸들러에서 이미 처리됨
          if (evt.code !== 1000 && evt.code !== 1001) {
            const msg = "연결이 예기치 않게 종료되었습니다.";
            setErrorMsg(msg);
            setStatus("error");
            cleanup();
          }
        };
      } catch (err) {
        if (!isActiveRef.current) return;
        const msg =
          err instanceof DOMException && err.name === "NotAllowedError"
            ? "마이크 권한이 필요합니다."
            : "실시간 STT 시작에 실패했습니다.";
        setErrorMsg(msg);
        setStatus("error");
        cleanup();
      }
    },
    [status, cleanup, setTranscript, setConsultationId, setIps],
  );

  const stop = useCallback(() => {
    if (status !== "recording") return;
    setStatus("stopping");
    // 오디오 먼저 중단 — 이후 청크가 WS로 가지 않도록
    workletRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    // finish 신호 → 서버가 후처리 후 "completed" 반환
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: "finish" }));
    }
  }, [status]);

  const reset = useCallback(() => {
    cleanup();
    setStatus("idle");
    setErrorMsg(null);
  }, [cleanup]);

  return { status, errorMsg, start, stop, reset };
}
