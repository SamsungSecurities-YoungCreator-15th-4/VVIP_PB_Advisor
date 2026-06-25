"use client";

import { AlertTriangle, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";

import {
  PORTFOLIOS,
  SCENARIO_BASE,
  SCENARIO_SENSITIVITY,
  SCENARIO_WARN,
} from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

// 출처: 2008 글로벌 금융위기 — Fed 기준금리 0~0.25%(2008.12), KRW/USD 고점 1,570원(2009.03)
// 출처: 2022 러우전쟁 — Fed 기준금리 4.5%(2022.12), KRW/USD 1,440원(2022.09)
const SCENARIO_PRESETS = [
  { key: "crisis" as const, label: "금융위기", ratePct: 0.25, fxKrw: 1570 },
  { key: "war" as const, label: "러우전쟁", ratePct: 4.5, fxKrw: 1440 },
] as const;
/** 우측 상단: 시나리오 Test — 금리·환율 슬라이더 */
export default function StressTestSection() {
  const {
    scenario,
    setScenario,
    liveBase,
    customers,
    selectedCustomerId,
    portfolios,
    basePortfolios,
    isStressMode,
    stressPreset,
    setStressPreset,
    analyzing,
  } = useDashboardStore();

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const aumEokwon = customer?.aumEokwon ?? 50;

  const rateDelta = scenario.ratePct - liveBase.ratePct;
  const fxDelta = scenario.fxKrw - liveBase.fxKrw;
  const isExtreme =
    Math.abs(rateDelta) >= SCENARIO_WARN.rateDeltaPct ||
    Math.abs(fxDelta) >= SCENARIO_WARN.fxDeltaKrw;

  const handleCurrentPreset = () => {
    setStressPreset("current");
    setScenario({ ratePct: liveBase.ratePct, fxKrw: liveBase.fxKrw });
    // clearStressMode는 분석하기 클릭 시 handleAnalyze(Sidebar)에서 처리
  };

  // 예상 평가손익 (연간 억원)
  // isStressMode: portfolios = stressed, basePortfolios = calculate 결과(기준선)
  const pnlEok = (id: "current" | "a" | "b") => {
    if (isStressMode) {
      const base = basePortfolios.find((p) => p.id === id);
      const stressed = portfolios.find((p) => p.id === id);
      if (base && stressed) {
        return (
          ((stressed.metrics.expectedReturnPct -
            base.metrics.expectedReturnPct) /
            100) *
          aumEokwon
        );
      }
    }
    // 폴백: 선형 민감도 (백엔드 미연결 시)
    const s = SCENARIO_SENSITIVITY[id];
    return s.perRatePct * rateDelta + s.perFxKrw * fxDelta;
  };

  return (
    <Card className="gap-0 p-3.5">
      {/* 헤더 */}
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[14px] font-bold">Stress Test</p>
        {isExtreme && (
          <div className="flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-[11px] font-bold text-red-600">
            <AlertTriangle className="size-3" />
            변동성 주의
          </div>
        )}
      </div>

      {/* 시나리오 프리셋 */}
      <div className="mb-3.5 flex rounded-lg bg-muted p-0.5">
        <button
          type="button"
          onClick={handleCurrentPreset}
          className={`flex-1 rounded-md py-1 text-[11px] font-bold transition-colors ${
            stressPreset === "current"
              ? "bg-white text-brand-dark shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          현재
        </button>
        {SCENARIO_PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => {
              setStressPreset(p.key);
              setScenario({ ratePct: p.ratePct, fxKrw: p.fxKrw });
            }}
            className={`flex-1 rounded-md py-1 text-[11px] font-bold transition-colors ${
              stressPreset === p.key
                ? "bg-white text-brand-dark shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <ScenarioSlider
        label="금리"
        valueLabel={`${scenario.ratePct.toFixed(2)}%`}
        delta={rateDelta}
        deltaLabel={`${rateDelta > 0 ? "+" : ""}${rateDelta.toFixed(2)}%p`}
        value={scenario.ratePct}
        min={SCENARIO_BASE.rateMin}
        max={SCENARIO_BASE.rateMax}
        step={SCENARIO_BASE.rateStep}
        minLabel={`${SCENARIO_BASE.rateMin.toFixed(1)}%`}
        maxLabel={`${SCENARIO_BASE.rateMax.toFixed(1)}%`}
        onChange={(v) => {
          setStressPreset(null);
          setScenario({ ratePct: v });
        }}
      />

      <ScenarioSlider
        label="환율"
        valueLabel={`${scenario.fxKrw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`}
        delta={fxDelta}
        deltaLabel={`${fxDelta > 0 ? "+" : ""}${fxDelta.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`}
        value={scenario.fxKrw}
        min={SCENARIO_BASE.fxMin}
        max={SCENARIO_BASE.fxMax}
        step={SCENARIO_BASE.fxStep}
        minLabel={SCENARIO_BASE.fxMin.toLocaleString()}
        maxLabel={SCENARIO_BASE.fxMax.toLocaleString()}
        onChange={(v) => {
          setStressPreset(null);
          setScenario({ fxKrw: v });
        }}
      />

      {/* 예상 평가손익 */}
      <div className="mt-3 rounded-xl bg-brand/5 p-3">
        <p className="mb-2 text-[13px] font-extrabold">예상 평가손익 (연간)</p>
        {analyzing ? (
          <div className="flex items-center justify-center gap-1.5 py-2 text-[12px] font-semibold text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            분석 중...
          </div>
        ) : !isStressMode ? (
          <p className="py-1 text-center text-[12px] font-semibold text-muted-foreground">
            분석하기 후 확인할 수 있습니다
          </p>
        ) : (
          PORTFOLIOS.map((pf) => {
            const raw = pnlEok(pf.id);
            const v = parseFloat(raw.toFixed(1));
            const label =
              pf.id === "current" ? "현재" : `제안 ${pf.id.toUpperCase()}`;
            return (
              <div
                key={pf.id}
                className="flex items-center justify-between py-1 text-[13px]"
              >
                <span className="font-semibold text-muted-foreground">
                  {label}
                </span>
                <span
                  className={`font-extrabold tabular-nums ${v < 0 ? "text-down" : v > 0 ? "text-up" : "text-foreground"}`}
                >
                  {v < 0 ? "▼ " : v > 0 ? "▲ " : ""}
                  {Math.abs(v).toFixed(1)}억원
                </span>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}

function ScenarioSlider({
  label,
  valueLabel,
  delta,
  deltaLabel,
  value,
  min,
  max,
  step,
  minLabel,
  maxLabel,
  onChange,
}: {
  label: string;
  valueLabel: string;
  delta: number;
  deltaLabel: string;
  value: number;
  min: number;
  max: number;
  step: number;
  minLabel: string;
  maxLabel: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[12px] font-bold text-muted-foreground">
          {label}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-extrabold">{valueLabel}</span>
          <span
            className={`text-[11px] font-bold ${delta === 0 ? "text-foreground" : delta > 0 ? "text-up" : "text-down"}`}
          >
            {deltaLabel}
          </span>
        </div>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => onChange(v)}
      />
      <div className="mt-0.5 flex justify-between text-[10px] text-muted-foreground/60">
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </div>
    </div>
  );
}
