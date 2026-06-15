"use client";

import { Lightbulb } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import {
  PORTFOLIOS,
  SCENARIO_BASE,
  SCENARIO_SENSITIVITY,
  SCENARIO_WARN,
} from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

/** 우측 상단: 시나리오 Test — 금리·환율 슬라이더와 예상 평가손익 */
export default function StressTestSection() {
  const { scenario, setScenario, resetScenario } = useDashboardStore();

  const rateDelta = scenario.ratePct - SCENARIO_BASE.ratePct;
  const fxDelta = scenario.fxKrw - SCENARIO_BASE.fxKrw;
  const isExtreme =
    Math.abs(rateDelta) >= SCENARIO_WARN.rateDeltaPct ||
    Math.abs(fxDelta) >= SCENARIO_WARN.fxDeltaKrw;

  // 더미 선형 민감도로 연간 평가손익(억원)을 추정 — 백엔드 시뮬레이션으로 교체 예정
  const pnlEok = (id: "current" | "a" | "b") => {
    const s = SCENARIO_SENSITIVITY[id];
    return s.perRatePct * rateDelta + s.perFxKrw * fxDelta;
  };

  return (
    <Card className="gap-0 p-3.5">
      <p className="mb-3 text-[14px] font-bold">시나리오 Test</p>

      <ScenarioSlider
        label="금리"
        valueLabel={`${scenario.ratePct.toFixed(2)}%`}
        delta={rateDelta}
        deltaLabel={`${rateDelta >= 0 ? "+" : ""}${rateDelta.toFixed(2)}%p`}
        value={scenario.ratePct}
        min={SCENARIO_BASE.rateMin}
        max={SCENARIO_BASE.rateMax}
        step={SCENARIO_BASE.rateStep}
        minLabel={`${SCENARIO_BASE.rateMin.toFixed(1)}%`}
        maxLabel={`${SCENARIO_BASE.rateMax.toFixed(1)}%`}
        resetLabel={`초기화 (현재 ${SCENARIO_BASE.ratePct}%)`}
        onChange={(v) => setScenario({ ratePct: v })}
        onReset={resetScenario}
      />

      <ScenarioSlider
        label="환율"
        valueLabel={`${scenario.fxKrw.toLocaleString()}원`}
        delta={fxDelta}
        deltaLabel={`${fxDelta >= 0 ? "+" : ""}${fxDelta.toLocaleString()}원`}
        value={scenario.fxKrw}
        min={SCENARIO_BASE.fxMin}
        max={SCENARIO_BASE.fxMax}
        step={SCENARIO_BASE.fxStep}
        minLabel={SCENARIO_BASE.fxMin.toLocaleString()}
        maxLabel={SCENARIO_BASE.fxMax.toLocaleString()}
        resetLabel={`초기화 (현재 ${SCENARIO_BASE.fxKrw.toLocaleString()}원)`}
        onChange={(v) => setScenario({ fxKrw: v })}
        onReset={resetScenario}
      />

      <div className="mt-1 rounded-xl bg-brand/5 p-3">
        <p className="mb-2 text-[13px] font-extrabold">예상 평가손익 (연간)</p>
        {PORTFOLIOS.map((pf) => {
          const v = pnlEok(pf.id);
          const label = pf.id === "current" ? "현재" : `제안 ${pf.id.toUpperCase()}`;
          return (
            <div
              key={pf.id}
              className="flex items-center justify-between py-1 text-[13px]"
            >
              <span className="font-semibold text-muted-foreground">
                {label}
              </span>
              <span
                className={`font-extrabold tabular-nums ${
                  v < 0 ? "text-down" : v > 0 ? "text-up" : "text-foreground"
                }`}
              >
                {v < 0 ? "▼ " : v > 0 ? "▲ " : ""}
                {Math.abs(v).toFixed(1)}억원
              </span>
            </div>
          );
        })}
      </div>

      {/* 기준 시나리오를 크게 벗어나면 경고 (조건부 렌더) */}
      {isExtreme && (
        <div className="mt-2 flex items-start gap-2 rounded-xl bg-muted p-3">
          <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <p className="text-[12px] font-semibold leading-snug text-muted-foreground">
            {SCENARIO_WARN.message}
          </p>
        </div>
      )}
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
  resetLabel,
  onChange,
  onReset,
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
  resetLabel: string;
  onChange: (v: number) => void;
  onReset: () => void;
}) {
  return (
    <div className="mb-3.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-bold text-muted-foreground">
          {label}
        </span>
        <span
          className={`text-lg font-extrabold tabular-nums ${
            delta > 0 ? "text-up" : delta < 0 ? "text-down" : "text-foreground"
          }`}
        >
          {valueLabel}{" "}
          {delta !== 0 && <span className="text-[13px]">({deltaLabel})</span>}
        </span>
      </div>
      <Slider
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        min={min}
        max={max}
        step={step}
        className="mt-2"
      />
      <div className="mt-1 flex justify-between text-[10px] font-semibold text-muted-foreground/70">
        <span className="tabular-nums">{minLabel}</span>
        <button
          type="button"
          onClick={onReset}
          className="font-bold hover:text-brand-dark"
        >
          {resetLabel}
        </button>
        <span className="tabular-nums">{maxLabel}</span>
      </div>
    </div>
  );
}
