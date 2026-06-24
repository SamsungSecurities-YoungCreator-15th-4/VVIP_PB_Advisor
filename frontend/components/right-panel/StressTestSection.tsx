"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { fetchMacroIndicators } from "@/lib/api";
import {
  PORTFOLIOS,
  SCENARIO_BASE,
  SCENARIO_SENSITIVITY,
  SCENARIO_WARN,
} from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import {
  BACKEND_PORTFOLIO_ID,
  useStressedPortfolios,
} from "@/lib/useStressedPortfolios";

// 위기 프리셋의 그 시대 금리·환율(슬라이더 표시용). 출처:
// 2008 금융위기 — Fed 기준금리 0~0.25%(2008.12), KRW/USD 고점 1,570원(2009.03)
// 2022 러우전쟁 — Fed 기준금리 4.5%(2022.12), KRW/USD 1,440원(2022.09)
// 단, 백엔드 계산은 슬라이더가 아니라 시나리오 충격벡터(crisis_*)로 한다.
const CRISIS_PRESETS = [
  { key: "crisis_2008" as const, label: "금융위기", ratePct: 0.25, fxKrw: 1570 },
  { key: "crisis_ru_war" as const, label: "러우전쟁", ratePct: 4.5, fxKrw: 1440 },
] as const;

/** 우측 상단: 시나리오 Test — 금리·환율 슬라이더와 예상 평가손익 */
export default function StressTestSection() {
  const {
    scenario,
    setScenario,
    liveBase,
    setLiveBase,
    activeScenario,
    applyCrisisPreset,
    appliedScenario,
    appliedActiveScenario,
  } = useDashboardStore();
  const { byId, failed, aumEokwon } = useStressedPortfolios();

  // pending(현재 슬라이더/버튼)이 applied(분석하기로 확정된 값)와 다르면 "변경됨".
  // 평가손익은 applied 기준으로만 계산되므로, 사용자에게 분석하기를 눌러야 갱신됨을 알린다.
  const dirty =
    scenario.ratePct !== appliedScenario.ratePct ||
    scenario.fxKrw !== appliedScenario.fxKrw ||
    activeScenario !== appliedActiveScenario;

  // 슬라이더 기준점을 실시간 현재값(기준금리·원/달러)으로 맞춘다.
  // 최초 1회 로드 시 store가 슬라이더도 실시간 값으로 스냅한다.
  useEffect(() => {
    fetchMacroIndicators()
      .then((d) =>
        setLiveBase({
          ratePct: d.baseRate.price,
          fxKrw: Math.round(d.krwUsd.price),
        }),
      )
      .catch(() => {
        /* 실패 시 목 기준값 유지 */
      });
  }, [setLiveBase]);

  const rateDelta = scenario.ratePct - liveBase.ratePct;
  const fxDelta = scenario.fxKrw - liveBase.fxKrw;
  const isExtreme =
    Math.abs(rateDelta) >= SCENARIO_WARN.rateDeltaPct ||
    Math.abs(fxDelta) >= SCENARIO_WARN.fxDeltaKrw;

  // 연간 예상 평가손익(억원) = (충격 후 기대수익률 − 기준 기대수익률) × 운용자산.
  // 백엔드 stress-metrics 실데이터(applied 기준)를 쓴다(슬라이더·위기 시나리오 모두).
  // expectedReturn은 %라 /100으로 소수 환산 후 운용자산(억)을 곱한다.
  const pnlEok = (id: "current" | "a" | "b"): number | null => {
    const live = byId[BACKEND_PORTFOLIO_ID[id]];
    if (!failed && live) {
      return (
        ((live.stressed.expectedReturn - live.base.expectedReturn) / 100) *
        aumEokwon
      );
    }
    // 백엔드 실패 폴백: 위기 시나리오는 더미 선형식으로 못 구함 → "분석 시 산출".
    if (appliedActiveScenario) return null;
    // 폴백 델타도 applied(분석하기로 확정된 값) 기준이어야 표시와 일치한다.
    const s = SCENARIO_SENSITIVITY[id];
    const appliedRateDelta = appliedScenario.ratePct - liveBase.ratePct;
    const appliedFxDelta = appliedScenario.fxKrw - liveBase.fxKrw;
    return s.perRatePct * appliedRateDelta + s.perFxKrw * appliedFxDelta;
  };

  return (
    <Card className="gap-0 p-3.5">
      {/* 헤더: 제목 + 극단 시나리오 경고 배지 */}
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[14px] font-bold">Stress Test</p>
        {isExtreme && (
          <div className="flex items-center gap-1 rounded-md bg-red-50 px-2 py-0.5 text-[11px] font-bold text-red-600">
            <AlertTriangle className="size-3" />
            변동성 주의
          </div>
        )}
      </div>

      {/* 시나리오 프리셋 세그먼트.
          현재=슬라이더 모드(기준값). 금융위기/러우전쟁=슬라이더가 그 시대 값으로 이동(표시)
          + 백엔드엔 시나리오 충격벡터(crisis_*) 전송. 슬라이더를 움직이면 위기 해제. */}
      <div className="mb-3.5">
        <div className="flex rounded-lg bg-muted p-0.5">
          <PresetTab
            label="현재"
            active={activeScenario === null}
            onClick={() =>
              setScenario({ ratePct: liveBase.ratePct, fxKrw: liveBase.fxKrw })
            }
          />
          {CRISIS_PRESETS.map((p) => (
            <PresetTab
              key={p.key}
              label={p.label}
              active={activeScenario === p.key}
              onClick={() =>
                applyCrisisPreset(p.key, { ratePct: p.ratePct, fxKrw: p.fxKrw })
              }
            />
          ))}
        </div>
        {activeScenario && (
          <p className="mt-1.5 text-[11px] font-semibold text-brand-dark">
            위기 시나리오 적용 중 · 슬라이더를 조정하면 해제됩니다
          </p>
        )}
      </div>

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
        onChange={(v) => setScenario({ ratePct: v })}
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
        onChange={(v) => setScenario({ fxKrw: v })}
      />

      <div className="mt-1 rounded-xl bg-brand/5 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[13px] font-extrabold">예상 평가손익 (연간)</p>
          {dirty && (
            <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
              변경됨 · 분석하기 필요
            </span>
          )}
        </div>
        {PORTFOLIOS.map((pf) => {
          const v = pnlEok(pf.id);
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
              {v === null ? (
                <span className="text-[12px] font-semibold text-muted-foreground/70">
                  분석 시 산출
                </span>
              ) : (
                <span
                  className={`font-extrabold tabular-nums ${
                    v < 0 ? "text-down" : v > 0 ? "text-up" : "text-foreground"
                  }`}
                >
                  {v < 0 ? "▼ " : v > 0 ? "▲ " : ""}
                  {Math.abs(v).toFixed(1)}억원
                </span>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function PresetTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex-1 rounded-md py-1 text-[11px] font-bold transition-colors ${
        active
          ? "bg-white text-brand-dark shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
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
        <span className="tabular-nums">{maxLabel}</span>
      </div>
    </div>
  );
}
