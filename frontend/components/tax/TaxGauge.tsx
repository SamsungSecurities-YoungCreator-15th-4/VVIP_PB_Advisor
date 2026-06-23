"use client";

import { useState } from "react";
import { Slider } from "@/components/ui/slider";
import { TAX_THRESHOLD } from "@/lib/mockData";

const fmt = (n: number) => Math.round(n).toLocaleString("ko-KR");

/**
 * 종합과세 임계선 탭 — 기타 금융소득 슬라이더 + 기준선 게이지 + 판정.
 * 기준선 2,000만원: 소득세법 제14조 제3항 제6호 (금융소득종합과세).
 * 그 외 수치(예상 배당 등)는 백엔드 연동 전 더미.
 */
export default function TaxGauge() {
  const {
    thresholdManwon,
    gaugeMaxManwon,
    otherIncomeDefault,
    otherIncomeMax,
    portfolioDividendManwon,
    separateRateLabel,
    comprehensiveRateLabel,
  } = TAX_THRESHOLD;

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
    const clamped = isNaN(parsed) ? 0 : Math.min(Math.max(parsed, 0), otherIncomeMax);
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
      <div className="flex items-stretch gap-2.5">
        <div className="flex-1 rounded-xl border p-3">
          <p className="text-[12px] font-bold text-muted-foreground">
            고객 기타 금융소득 입력 (연 이자·배당)
          </p>
          <div className="mt-1 flex items-baseline gap-1">
            <input
              type="text"
              inputMode="numeric"
              value={inputVal}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              className="w-32 border-b-2 border-brand bg-transparent text-lg font-extrabold tabular-nums outline-none"
            />
            <span className="text-[12px] font-bold text-muted-foreground">만원</span>
          </div>
          <Slider
            value={[otherIncome]}
            onValueChange={([v]) => handleSliderChange(v)}
            min={0}
            max={otherIncomeMax}
            step={10}
            className="mt-2"
          />
        </div>
        <div className="w-[130px] rounded-xl border bg-brand/5 p-3">
          <p className="text-[12px] font-bold text-muted-foreground">
            포트폴리오 A<br />
            예상 이자·배당
          </p>
          <p className="mt-1 text-sm font-extrabold tabular-nums text-brand-dark">
            +{fmt(portfolioDividendManwon)}
            <span className="text-[12px]">만원</span>
          </p>
          <p className="mt-0.5 text-[12px] font-semibold text-muted-foreground">
            합산 대상 과세소득
          </p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-[12px] font-bold text-muted-foreground">
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
            <p className="text-[12px] font-extrabold">
              기준선 <b className="text-up">초과</b> — 금융소득종합과세 대상
            </p>
            <p className="mt-0.5 text-[12px] font-semibold leading-snug text-muted-foreground">
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
            <p className="text-[12px] font-extrabold">
              기준선 <b className="text-brand-dark">이내</b> — 분리과세 유지
            </p>
            <p className="mt-0.5 text-[12px] font-semibold leading-snug text-muted-foreground">
              합산 금융소득이 기준선 {fmt(thresholdManwon)}만원 이내로,{" "}
              <b>15.4% 분리과세</b>가 적용됩니다. 여유 한도{" "}
              <b>{fmt(thresholdManwon - total)}만원</b>.
            </p>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <div className="flex-1 rounded-lg border p-2 text-center">
          <p className="text-[12px] font-bold text-muted-foreground">
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
          <p className="text-[12px] font-bold text-muted-foreground">
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
