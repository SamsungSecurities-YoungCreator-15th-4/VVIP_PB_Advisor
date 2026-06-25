"use client";

// 상단 헤더의 거시지표 6종 — 백엔드 /api/macro-indicators 실데이터로 표시.
// 연결 실패 시 목데이터로 폴백하고, 실시간 조회 실패분은 "지연" 표시한다.
import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";

import { fetchMacroIndicators } from "@/lib/api";
import { MACRO_INDICATORS } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import type { IndicatorData, MacroIndicators } from "@/lib/types";

interface Row {
  label: string;
  value: string;
  change: string;
  direction: "up" | "down" | "neutral";
  note?: string;
}

const sign = (n: number) => (n > 0 ? "+" : "");

// 백엔드 MacroIndicators(소수/원시값)를 헤더 표시용 6행으로 변환
function toRows(d: MacroIndicators): Row[] {
  const num = (v: number, frac = 0) =>
    v.toLocaleString("ko-KR", { maximumFractionDigits: frac });

  const mk = (
    label: string,
    item: IndicatorData,
    value: string,
    change: string,
  ): Row => ({
    label,
    value: item.price === 0 ? "—" : value,
    change,
    direction: item.change > 0 ? "up" : item.change < 0 ? "down" : "neutral",
    note: item.isStatic
      ? "발표 기준"
      : item.isFallback
        ? "지연 시세"
        : undefined,
  });

  return [
    mk(
      "미국 기준금리",
      d.baseRate,
      `${d.baseRate.price.toFixed(2)}%`,
      `${sign(d.baseRate.change)}${d.baseRate.change.toFixed(2)}%p`,
    ),
    mk(
      "미 10Y",
      d.treasuryYield,
      `${d.treasuryYield.price.toFixed(2)}%`,
      `${sign(d.treasuryYield.change)}${d.treasuryYield.change.toFixed(2)}%p`,
    ),
    mk(
      "미국 CPI",
      d.cpi,
      `${d.cpi.price.toFixed(1)}%`,
      `${sign(d.cpi.change)}${d.cpi.change.toFixed(2)}%p`,
    ),
    mk(
      "원/달러",
      d.krwUsd,
      num(d.krwUsd.price),
      `${sign(d.krwUsd.change)}${num(Math.round(d.krwUsd.change))}원`,
    ),
    mk(
      "KOSPI",
      d.kospi,
      num(d.kospi.price),
      `${sign(d.kospi.change)}${d.kospi.change.toFixed(2)}`,
    ),
    mk(
      "S&P 500",
      d.sp500,
      num(d.sp500.price),
      `${sign(d.sp500.change)}${d.sp500.change.toFixed(2)}`,
    ),
  ];
}

// 백엔드 연결 전/실패 시 폴백 (목데이터를 동일 형태로 변환)
const FALLBACK_ROWS: Row[] = MACRO_INDICATORS.map((m) => ({
  label: m.label,
  value: m.value,
  change: m.change,
  direction: m.direction,
}));

// ISO(UTC) → "HH:MM" (KST) 기준 시각 표기
function toKstHM(iso: string | null): string {
  if (!iso) return "--:--";
  return new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  });
}

const REFRESH_COOLDOWN_MS = 30_000; // 강제 새로고침 연타 방지 쿨다운

export default function MacroTicker() {
  const [rows, setRows] = useState<Row[]>(FALLBACK_ROWS);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cooling, setCooling] = useState(false);
  const cancelledRef = useRef(false);
  const setLiveBase = useDashboardStore((s) => s.setLiveBase);
  const setMacroIndicators = useDashboardStore((s) => s.setMacroIndicators);

  // force=true면 백엔드 5분 캐시를 무시하고 강제 재조회
  const load = (force: boolean) => {
    setLoading(true);
    return fetchMacroIndicators(force)
      .then((d) => {
        if (cancelledRef.current) return;
        const liveRows = toRows(d);
        setRows(liveRows);
        // PDF 등 다른 화면이 같은 실시간 지표를 읽도록 store 에도 올린다.
        setMacroIndicators(liveRows);
        setFetchedAt(d.fetchedAt); // 데이터 기준 시각 동기화
        // 슬라이더 기준점을 실데이터로 업데이트 (최초 1회는 scenario도 스냅)
        setLiveBase({ ratePct: d.baseRate.price, fxKrw: Math.round(d.krwUsd.price) });
      })
      .catch(() => {
        /* 폴백 행 유지 */
      })
      .finally(() => {
        if (!cancelledRef.current) setLoading(false);
      });
  };

  useEffect(() => {
    cancelledRef.current = false;
    const t = setTimeout(() => load(false), 0); // 마운트 1회
    const id = setInterval(() => load(false), 5 * 60 * 1000); // 5분 자동 갱신
    return () => {
      cancelledRef.current = true;
      clearTimeout(t);
      clearInterval(id);
    };
  // load를 dep에 넣으면 매 렌더마다 interval이 재생성되므로 의도적으로 마운트 1회만 실행
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 새로고침 버튼: 클릭 시각 즉시 표시 → 강제 갱신 + 쿨다운
  const onRefresh = () => {
    if (loading || cooling) return;
    setFetchedAt(new Date().toISOString()); // 버튼 누른 시각으로 먼저 표시
    load(true);
    setCooling(true);
    setTimeout(() => {
      if (!cancelledRef.current) setCooling(false);
    }, REFRESH_COOLDOWN_MS);
  };

  return (
    <>
      {/* 데이터 기준 시각 + 강제 새로고침 */}
      <div className="flex shrink-0 items-center gap-1 border-r pr-4 pl-2 text-[10px] font-semibold text-muted-foreground">
        <span>기준</span>
        <b className="text-[11px] font-bold tabular-nums text-foreground">
          {toKstHM(fetchedAt)}
        </b>
        <button
          onClick={onRefresh}
          disabled={loading || cooling}
          aria-label="거시지표 새로고침"
          title={cooling ? "잠시 후 다시 시도" : "지표 강제 새로고침"}
          className="ml-0.5 rounded p-0.5 text-foreground transition-colors hover:text-foreground disabled:opacity-40"
        >
          <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      {rows.map((m) => (
        <div
          key={m.label}
          className="shrink-0 border-r px-4 last:border-none first:pl-2"
        >
          <div className="text-[10px] font-semibold text-muted-foreground">
            {m.label}
          </div>
          <div className="text-base font-extrabold leading-none tabular-nums">
            {m.value}
          </div>
          {m.note ? (
            <div className="mt-0.5 text-[10px] font-semibold text-muted-foreground">
              {m.note}
            </div>
          ) : (
            <div
              className={`mt-0.5 text-[10px] font-bold tabular-nums ${
                m.direction === "up"
                  ? "text-up"
                  : m.direction === "down"
                    ? "text-down"
                    : "text-foreground"
              }`}
            >
              {m.direction === "up" ? "▲ " : m.direction === "down" ? "▼ " : ""}
              {m.change}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
