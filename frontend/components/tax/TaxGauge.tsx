"use client";

import { useState } from "react";
import { Slider } from "@/components/ui/slider";
import { TAX_THRESHOLD } from "@/lib/mockData";
import type { StressTaxGauge } from "@/lib/api";

const fmt = (n: number) => Math.round(n).toLocaleString("ko-KR");

interface Props {
  /** stressed_tax.financial_income_tax_gauge — 제공 시 실데이터 사용 */
  gaugeData?: StressTaxGauge | null;
}

/**
 * 종합과세 임계선 탭 — 기타 금융소득 슬라이더 + 기준선 게이지 + 판정.
 * 기준선 2,000만원: 소득세법 제14조 제3항 제6호 (금융소득종합과세).
 * gaugeData 제공 시 API 실데이터 사용, 없으면 mock 폴백.
 */
export default function TaxGauge({ gaugeData }: Props) {
  const mock = TAX_THRESHOLD;
  const thresholdManwon    = gaugeData?.threshold_manwon            ?? mock.thresholdManwon;
  const gaugeMaxManwon     = Math.max(thresholdManwon * 1.5, mock.gaugeMaxManwon);
  const otherIncomeDefault = gaugeData?.external_financial_income_manwon ?? mock.otherIncomeDefault;
  const otherIncomeMax     = Math.max(gaugeMaxManwon, mock.otherIncomeMax);
  const portfolioDividendManwon = gaugeData?.portfolio_financial_income_manwon ?? mock.portfolioDividendManwon;
  const separateRateLabel      = gaugeData?.separate_rate_label      ?? mock.separateRateLabel;
  const comprehensiveRateLabel = gaugeData?.comprehensive_rate_label ?? mock.comprehensiveRateLabel;

  const [otherIncome, setOtherIncome] = useState(otherIncomeDefault);
  const [inputVal, setInputVal] = useState(String(otherIncomeDefault));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9]/g, "");
    setInputVal(raw);
    const parsed = parseInt(raw, 10);
    if (!isNaN(parsed)) {
      setOtherIncome(Math.min(parsed, otherIncomeMax));
    }
  };

  const handleInputBlur = () => {
    if (inputVal === "") {
      setOtherIncome(0);
      setInputVal("0");
      return;
    }
    const parsed = parseInt(inputVal, 10);
    const clamped = isNaN(parsed)
      ? 0
      : Math.min(Math.max(parsed, 0), otherIncomeMax);
    setOtherIncome(clamped);
    setInputVal(String(clamped));
  };

  const handleSliderChange = (v: number) => {
    setOtherIncome(v);
    setInputVal(String(v));
  };

  const total = otherIncome + portfolioDividendManwon;
  const isOver = total > thresholdManwon;
  const totalPct = (Math.min(total, gaugeMaxManwon) / gaugeMaxManwon) * 100;
  const thresholdPct = (thresholdManwon / gaugeMaxManwon) * 100;

  return (
    <div className="flex flex-col gap-3">
      {/* 입력 + 포트폴리오 */}
      <div className="flex items-stretch gap-3">
        <div className="flex-1 rounded-xl border p-4">
          <p className="text-[13px] font-bold text-muted-foreground">
            고객 기타 금융소득 입력
          </p>
          <div className="mt-2 flex items-baseline gap-1.5">
            <input
              type="text"
              inputMode="numeric"
              value={inputVal}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              className="w-36 rounded-md border border-border bg-transparent px-2 py-1 text-xl font-extrabold tabular-nums outline-none focus:border-brand"
            />
            <span className="text-[13px] font-bold text-muted-foreground">
              만원
            </span>
          </div>
          <Slider
            value={[otherIncome]}
            onValueChange={([v]) => handleSliderChange(v)}
            min={0}
            max={otherIncomeMax}
            step={10}
            className="mt-3"
          />
        </div>
        <div className="w-[140px] rounded-xl border bg-brand/5 p-4">
          <p className="text-[13px] font-bold text-muted-foreground">
            포트폴리오 A
          </p>
          <p className="mt-2 text-[15px] font-extrabold tabular-nums text-brand-dark">
            +{fmt(portfolioDividendManwon)}
            <span className="text-[13px]">만원</span>
          </p>
          <p className="mt-1 text-[13px] font-semibold text-muted-foreground">
            합산 대상 과세소득
          </p>
        </div>
      </div>

      {/* 게이지 */}
      <div>
        <div className="flex justify-between text-[13px] font-bold text-muted-foreground">
          <span>연 금융소득 합산</span>
          <span className="tabular-nums">{fmt(total)}만원</span>
        </div>
        <div className="relative mt-2 h-10">
          <div className="absolute inset-x-0 top-3 h-4 overflow-hidden rounded-md bg-muted">
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
            className="absolute top-0.5 h-9 w-0.5 bg-foreground"
            style={{ left: `${thresholdPct}%` }}
          >
            <span className="absolute -top-0.5 left-1.5 whitespace-nowrap text-[10px] font-extrabold">
              기준선 {fmt(thresholdManwon)}만
            </span>
          </div>
          <span
            className={`absolute top-7 -translate-x-1/2 whitespace-nowrap text-[11px] font-extrabold tabular-nums ${
              isOver ? "text-up" : "text-brand-dark"
            }`}
            style={{ left: `${totalPct}%` }}
          >
            {isOver ? "▲ " : ""}
            {fmt(total)}만
          </span>
        </div>
      </div>

      {/* 판정 알림 */}
      {isOver ? (
        <div className="flex items-start gap-3 rounded-xl bg-[#FEECEE] p-4">
          <svg
            className="mt-0.5 size-5 shrink-0"
            viewBox="0 0 20 20"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M10 2L1 18h18L10 2z"
              stroke="#F04452"
              strokeWidth="1.5"
              strokeLinejoin="round"
              fill="none"
            />
            <line
              x1="10"
              y1="8.5"
              x2="10"
              y2="13"
              stroke="#F04452"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <circle cx="10" cy="15.5" r="0.85" fill="#F04452" />
          </svg>
          <div>
            <p className="text-[14px] font-extrabold">
              기준선 <b className="text-up">초과</b> — 금융소득종합과세 대상
            </p>
            <p className="mt-1 text-[13px] font-semibold leading-relaxed text-muted-foreground">
              초과분 <b>{fmt(total - thresholdManwon)}만원</b>은 다른 종합소득과
              합산되어 최고 <b>49.5%</b>(지방소득세 포함) 누진세율이 적용됩니다.{" "}
              <b>절세 제안</b> 탭의 자산 이전으로 분리과세 전환을 권장합니다.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-xl bg-brand/5 p-4">
          <span className="text-base text-brand-dark">✓</span>
          <div>
            <p className="text-[14px] font-extrabold">
              기준선 <b className="text-brand-dark">이내</b> — 분리과세 유지
            </p>
            <p className="mt-1 text-[13px] font-semibold leading-relaxed text-muted-foreground">
              합산 금융소득이 기준선 {fmt(thresholdManwon)}만원 이내로,{" "}
              <b>15.4% 분리과세</b>가 적용됩니다. 여유 한도{" "}
              <b>{fmt(thresholdManwon - total)}만원</b>.
            </p>
          </div>
        </div>
      )}

      {/* 세율 요약 바 */}
      <div className="flex gap-2">
        <div
          className={`flex flex-1 items-center justify-between rounded-lg border px-3 py-2 ${
            !isOver
              ? "border-brand/20 bg-brand/5"
              : "border-transparent bg-muted/50"
          }`}
        >
          <span className="text-[13px] font-bold text-muted-foreground">
            분리과세 시
          </span>
          <span className="text-[15px] font-extrabold tabular-nums text-down">
            {separateRateLabel}
          </span>
        </div>
        <div
          className={`flex flex-1 items-center justify-between rounded-lg border px-3 py-2 ${
            isOver
              ? "border-brand/20 bg-brand/5"
              : "border-transparent bg-muted/50"
          }`}
        >
          <span className="text-[13px] font-bold text-muted-foreground">
            종합과세 시
          </span>
          <span className="text-[15px] font-extrabold tabular-nums text-down">
            {comprehensiveRateLabel}
          </span>
        </div>
      </div>
    </div>
  );
}
