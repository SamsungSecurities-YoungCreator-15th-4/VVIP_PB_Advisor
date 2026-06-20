"use client";

import { Slider } from "@/components/ui/slider";
import { PORTFOLIOS, TAX_THRESHOLD } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import {
  BACKEND_PORTFOLIO_ID,
  useStressedPortfolios,
} from "@/lib/useStressedPortfolios";

const fmt = (n: number) => Math.round(n).toLocaleString("ko-KR");

/**
 * 종합과세 임계선 탭 — 기타 금융소득 입력 + 기준선 게이지 + 판정.
 * 기준선 2,000만원: 소득세법 제14조 제3항 제6호 (금융소득종합과세).
 * 기타 금융소득은 store, 포트폴리오 예상 이자·배당은 백엔드 실데이터(dividendIncome).
 */
export default function TaxGauge() {
  const {
    thresholdManwon,
    otherIncomeMax,
    portfolioDividendManwon,
    separateRateLabel,
    comprehensiveRateLabel,
  } = TAX_THRESHOLD;

  const otherIncome = useDashboardStore((s) => s.otherIncomeManwon);
  const setOtherIncome = useDashboardStore((s) => s.setOtherIncome);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const { byId, failed } = useStressedPortfolios();

  // 선택 포트폴리오의 실제 연간 이자·배당(억→만원). 미연결 시 목값 폴백.
  const live = byId[BACKEND_PORTFOLIO_ID[selectedPortfolioId]];
  const portfolioDividend =
    !failed && live ? Math.round(live.dividendIncome * 10000) : portfolioDividendManwon;
  const pfName =
    PORTFOLIOS.find((p) => p.id === selectedPortfolioId)?.name ?? "포트폴리오";

  const total = otherIncome + portfolioDividend;
  const isOver = total > thresholdManwon;
  // 게이지 최대치는 합산소득에 맞춰 동적으로(기준선이 항상 보이도록).
  const gaugeMaxManwon = Math.max(3000, Math.ceil((total * 1.15) / 100) * 100);
  const totalPct = (Math.min(total, gaugeMaxManwon) / gaugeMaxManwon) * 100;
  const thresholdPct = (thresholdManwon / gaugeMaxManwon) * 100;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-stretch gap-2.5">
        <div className="flex-1 rounded-xl border p-3">
          <p className="text-[9.5px] font-bold text-muted-foreground">
            고객 기타 금융소득 입력 (연 이자·배당)
          </p>
          <div className="mt-1 flex items-baseline gap-1">
            <input
              type="number"
              min={0}
              step={10}
              value={otherIncome}
              onChange={(e) =>
                setOtherIncome(e.target.value === "" ? 0 : Number(e.target.value))
              }
              className="w-24 rounded-md border bg-card px-1.5 py-0.5 text-lg font-extrabold tabular-nums outline-none focus:border-brand focus:ring-1 focus:ring-brand [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
            <span className="text-[11px] font-bold text-muted-foreground">만원</span>
          </div>
          <Slider
            value={[Math.min(otherIncome, otherIncomeMax)]}
            onValueChange={([v]) => setOtherIncome(v)}
            min={0}
            max={otherIncomeMax}
            step={10}
            className="mt-2"
          />
        </div>
        <div className="w-[130px] rounded-xl border bg-brand/5 p-3">
          <p className="text-[9.5px] font-bold text-muted-foreground">
            {pfName}
            <br />
            예상 이자·배당
          </p>
          <p className="mt-1 text-sm font-extrabold tabular-nums text-brand-dark">
            +{fmt(portfolioDividend)}
            <span className="text-[11px]">만원</span>
          </p>
          <p className="mt-0.5 text-[8.5px] font-semibold text-muted-foreground">
            합산 대상 과세소득
          </p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-[9.5px] font-bold text-muted-foreground">
          <span>연 금융소득 합산</span>
          <span className="tabular-nums">{fmt(total)}만원</span>
        </div>
        <div className="relative mt-1 h-9">
          <div className="absolute inset-x-0 top-2.5 h-3 overflow-hidden rounded-md bg-muted">
            <div
              className="absolute left-0 top-0 h-full bg-linear-to-r from-[#2C7BFF] to-brand"
              style={{ width: `${Math.min(totalPct, thresholdPct)}%` }}
            />
            {isOver && (
              <div
                className="absolute top-0 h-full bg-up"
                style={{
                  left: `${thresholdPct}%`,
                  width: `${totalPct - thresholdPct}%`,
                }}
              />
            )}
          </div>
          <div
            className="absolute top-0.5 h-8 w-0.5 bg-foreground"
            style={{ left: `${thresholdPct}%` }}
          >
            <span className="absolute -top-0.5 left-1.5 whitespace-nowrap text-[8.5px] font-extrabold">
              기준선 {fmt(thresholdManwon)}만
            </span>
          </div>
          <span
            className={`absolute top-6 -translate-x-1/2 whitespace-nowrap text-[9px] font-extrabold tabular-nums ${
              isOver ? "text-up" : "text-brand-dark"
            }`}
            style={{ left: `${totalPct}%` }}
          >
            {isOver ? "▲ " : ""}
            {fmt(total)}만
          </span>
        </div>
      </div>

      {isOver ? (
        <div className="flex items-start gap-2 rounded-xl bg-[#FEECEE] p-3">
          <span className="text-sm">⚠️</span>
          <div>
            <p className="text-[11px] font-extrabold">
              기준선 <b className="text-up">초과</b> — 금융소득종합과세 대상
            </p>
            <p className="mt-0.5 text-[9.5px] font-semibold leading-snug text-muted-foreground">
              초과분 <b>{fmt(total - thresholdManwon)}만원</b>은 다른
              종합소득과 합산되어 최고 <b>49.5%</b>(지방소득세 포함) 누진세율이
              적용됩니다. <b>절세 제안</b> 탭의 자산 이전으로 분리과세 전환을
              권장합니다.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-xl bg-brand/5 p-3">
          <span className="text-sm text-brand-dark">✓</span>
          <div>
            <p className="text-[11px] font-extrabold">
              기준선 <b className="text-brand-dark">이내</b> — 분리과세 유지
            </p>
            <p className="mt-0.5 text-[9.5px] font-semibold leading-snug text-muted-foreground">
              합산 금융소득이 기준선 {fmt(thresholdManwon)}만원 이내로,{" "}
              <b>15.4% 분리과세</b>가 적용됩니다. 여유 한도{" "}
              <b>{fmt(thresholdManwon - total)}만원</b>.
            </p>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <div className="flex-1 rounded-lg border p-2 text-center">
          <p className="text-[9px] font-bold text-muted-foreground">
            분리과세 시
          </p>
          <p className="mt-0.5 text-[15px] font-extrabold tabular-nums text-down">
            {separateRateLabel}
          </p>
        </div>
        <div
          className={`flex-1 rounded-lg border p-2 text-center ${
            isOver ? "border-[#F7B2B8] bg-[#FEF4F5]" : ""
          }`}
        >
          <p className="text-[9px] font-bold text-muted-foreground">
            종합과세 시 {isOver && "(현 상태)"}
          </p>
          <p className="mt-0.5 text-[15px] font-extrabold tabular-nums text-up">
            {comprehensiveRateLabel}
          </p>
        </div>
      </div>
    </div>
  );
}
