"use client";

// 시나리오 슬라이더(금리·환율) 값을 백엔드(/api/stressed-portfolios)로 보내
// 포트폴리오 3종의 전체 지표를 충격 주입 후 재계산해 받아오는 훅.
// 슬라이더가 0이면 base==stressed 이므로 항상 stressed를 표시하면 된다.
import { useEffect, useState } from "react";

import { fetchStressedPortfolios } from "./api";
import { useDashboardStore } from "./store";
import type { StressedPortfolio } from "./types";

// 프론트 포트폴리오 id(current/a/b) → 백엔드 id(current/proposalA/proposalB)
export const BACKEND_PORTFOLIO_ID: Record<string, string> = {
  current: "current",
  a: "proposalA",
  b: "proposalB",
};

export interface UseStressedResult {
  /** 백엔드 id → 충격 적용 결과 */
  byId: Record<string, StressedPortfolio>;
  loading: boolean;
  /** 백엔드 연결 실패 시 true → 호출부는 목데이터로 폴백 */
  failed: boolean;
  aumEokwon: number;
  hasScenario: boolean;
}

export function useStressedPortfolios(): UseStressedResult {
  const scenario = useDashboardStore((s) => s.scenario);
  const liveBase = useDashboardStore((s) => s.liveBase);
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  const otherIncomeManwon = useDashboardStore((s) => s.otherIncomeManwon);

  const customer = customers.find((c) => c.id === selectedCustomerId);
  const aumEokwon = customer?.aumEokwon ?? 50;
  // 만원 → 억 변환 (백엔드는 억 단위)
  const otherIncomeEok = otherIncomeManwon / 10000;
  // 고객의 절세계좌 기납입액·세부담 입력 — 절세 제안 실계산 파라미터
  const isaUsedManwon = customer?.isaUsedManwon ?? 0;
  const pensionUsedManwon = customer?.pensionUsedManwon ?? 0;
  const realizedLossManwon = customer?.realizedLossManwon ?? 0;
  const marginalRatePct = customer?.marginalRatePct ?? 38.5;
  // 적합성(lock-up) 게이팅 입력
  const age = customer?.age ?? null;
  const horizonYears = customer?.horizonYears ?? null;
  const nearTermNeedManwon = customer?.nearTermNeedManwon ?? 0;
  const nearTermNeedYears = customer?.nearTermNeedYears ?? null;
  const isaOpened = customer?.isaOpened ?? true;

  // 충격 델타는 실시간 현재값(liveBase) 기준으로 계산한다.
  const rateDeltaBp = Math.round((scenario.ratePct - liveBase.ratePct) * 100);
  const fxDelta = Math.round(scenario.fxKrw - liveBase.fxKrw);
  const hasScenario = rateDeltaBp !== 0 || fxDelta !== 0;

  const [byId, setById] = useState<Record<string, StressedPortfolio>>({});
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // 슬라이더 드래그 연사 방지용 디바운스 (setState는 effect 본문이 아닌
    // 타임아웃 콜백 안에서 호출 — react-hooks/set-state-in-effect 회피)
    const timer = setTimeout(() => {
      if (cancelled) return;
      setLoading(true);
      fetchStressedPortfolios(rateDeltaBp, fxDelta, aumEokwon, otherIncomeEok, {
        isaUsedManwon,
        pensionUsedManwon,
        realizedLossManwon,
        marginalRatePct,
        age: age ?? undefined,
        horizonYears: horizonYears ?? undefined,
        nearTermNeedManwon,
        nearTermNeedYears,
        isaOpened,
      })
        .then((list) => {
          if (cancelled) return;
          setById(Object.fromEntries(list.map((p) => [p.id, p])));
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
  }, [
    rateDeltaBp,
    fxDelta,
    aumEokwon,
    otherIncomeEok,
    isaUsedManwon,
    pensionUsedManwon,
    realizedLossManwon,
    marginalRatePct,
    age,
    horizonYears,
    nearTermNeedManwon,
    nearTermNeedYears,
    isaOpened,
  ]);

  return { byId, loading, failed, aumEokwon, hasScenario };
}
