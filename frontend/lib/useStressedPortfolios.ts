"use client";

// 시나리오 충격(슬라이더 금리·환율 또는 위기 버튼)을 백엔드 /portfolio/stress-metrics로
// 보내, 포트폴리오 3종(current/a/b)의 base/stressed 6대 지표를 받아온다.
// 비중은 화면 mock(11종)을 백엔드 canonical(12종)로 매핑해 보낸다.
// 비중 고정 → 지표만 재계산이므로 리밸런싱은 하지 않는다.
import { useEffect, useState } from "react";

import { fetchStressMetrics, type StressMode } from "./api/stress";
import { toBackendWeights } from "./assetMapping";
import { PORTFOLIOS } from "./mockData";
import { useDashboardStore } from "./store";
import type { PortfolioMetrics } from "./types";

// 프론트 포트폴리오 id(current/a/b) → 백엔드 id(current/proposalA/proposalB)
export const BACKEND_PORTFOLIO_ID: Record<string, string> = {
  current: "current",
  a: "proposalA",
  b: "proposalB",
};

/** 충격 전/후 6대 지표 쌍. */
export interface StressedPair {
  base: PortfolioMetrics;
  stressed: PortfolioMetrics;
}

export interface UseStressedResult {
  /** 백엔드 id → 충격 적용 결과(base/stressed) */
  byId: Record<string, StressedPair>;
  loading: boolean;
  /** 백엔드 연결 실패 시 true → 호출부는 더미 폴백 */
  failed: boolean;
  aumEokwon: number;
  /** 슬라이더가 움직였거나 위기 버튼이 켜졌으면 true */
  hasScenario: boolean;
}

export function useStressedPortfolios(): UseStressedResult {
  const scenario = useDashboardStore((s) => s.scenario);
  const liveBase = useDashboardStore((s) => s.liveBase);
  const activeScenario = useDashboardStore((s) => s.activeScenario);
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);

  const customer = customers.find((c) => c.id === selectedCustomerId);
  const aumEokwon = customer?.aumEokwon ?? 50;

  // 충격 델타는 실시간 현재값(liveBase) 기준.
  const rateDeltaBp = Math.round((scenario.ratePct - liveBase.ratePct) * 100);
  const fxDelta = Math.round(scenario.fxKrw - liveBase.fxKrw);
  const hasScenario = activeScenario != null || rateDeltaBp !== 0 || fxDelta !== 0;

  const [byId, setById] = useState<Record<string, StressedPair>>({});
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // 슬라이더 연사 방지 디바운스 (setState는 타임아웃 콜백 안에서)
    const timer = setTimeout(() => {
      if (cancelled) return;
      setLoading(true);

      // 위기 버튼이 켜져 있으면 시나리오 모드, 아니면 슬라이더 모드(상호배타).
      const mode: StressMode = activeScenario
        ? { kind: "scenario", scenario: activeScenario }
        : {
            kind: "slider",
            rateShock: rateDeltaBp / 10000, // bp → 소수 (100bp = 0.01)
            fxShock: liveBase.fxKrw ? fxDelta / liveBase.fxKrw : 0,
          };

      Promise.all(
        PORTFOLIOS.map((pf) =>
          fetchStressMetrics(toBackendWeights(pf.weights), mode, {
            totalAssetEok: aumEokwon,
          }).then(
            (r) =>
              [
                BACKEND_PORTFOLIO_ID[pf.id],
                { base: r.base, stressed: r.stressed },
              ] as const,
          ),
        ),
      )
        .then((entries) => {
          if (cancelled) return;
          setById(Object.fromEntries(entries));
          setFailed(false);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [rateDeltaBp, fxDelta, activeScenario, aumEokwon, liveBase.fxKrw]);

  return { byId, loading, failed, aumEokwon, hasScenario };
}
