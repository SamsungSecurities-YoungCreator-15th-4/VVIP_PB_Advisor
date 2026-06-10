'use client';

import { useState, useEffect } from 'react';
import { fetchMacroIndicators } from '@/lib/api';
import type { IndicatorData, MacroIndicators as MacroData } from '@/lib/types';

const TICKER_CONFIG = [
  { key: 'baseRate',      label: '기준금리',   unit: '%',  fmt: (v: number) => v.toFixed(2),                                                   fmtChange: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%p` },
  { key: 'treasuryYield', label: '미국 10Y',   unit: '%',  fmt: (v: number) => v.toFixed(2),                                                   fmtChange: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(3)}%p` },
  { key: 'krwUsd',        label: '원/달러',    unit: '원', fmt: (v: number) => v.toLocaleString('ko-KR', { maximumFractionDigits: 0 }),         fmtChange: (v: number) => `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('ko-KR')}원` },
  { key: 'cpi',           label: 'CPI',        unit: '%',  fmt: (v: number) => v.toFixed(1),                                                   fmtChange: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%p` },
  { key: 'kospi',         label: 'KOSPI',      unit: '',   fmt: (v: number) => v.toLocaleString('ko-KR', { maximumFractionDigits: 0 }),         fmtChange: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}` },
  { key: 'sp500',         label: 'S&P 500',    unit: '',   fmt: (v: number) => v.toLocaleString('ko-KR', { maximumFractionDigits: 0 }),         fmtChange: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}` },
];

function applyMacroData(
  json: MacroData,
  setData: (d: MacroData) => void,
  setUpdatedAt: (t: string) => void,
) {
  setData(json);
  if (json.fetchedAt) {
    const d = new Date(json.fetchedAt);
    setUpdatedAt(`${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`);
  }
}

export default function HeaderTicker() {
  const [data, setData] = useState<MacroData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  // 초기 로드 + 5분 자동 갱신
  useEffect(() => {
    fetchMacroIndicators()
      .then((json) => applyMacroData(json, setData, setUpdatedAt))
      .catch(() => {})
      .finally(() => setIsLoading(false));

    const interval = setInterval(() => {
      fetchMacroIndicators()
        .then((json) => applyMacroData(json, setData, setUpdatedAt))
        .catch(() => {});
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  // 수동 새로고침
  const handleRefresh = () => {
    setIsRefreshing(true);
    fetchMacroIndicators()
      .then((json) => applyMacroData(json, setData, setUpdatedAt))
      .catch(() => {})
      .finally(() => setIsRefreshing(false));
  };

  return (
    <div className="flex items-center gap-1.5">
      {updatedAt && (
        <span className="text-[10px] text-gray-600 whitespace-nowrap">{updatedAt} 기준</span>
      )}
      <button
        onClick={handleRefresh}
        disabled={isRefreshing}
        className="flex items-center justify-center w-6 h-6 rounded-md bg-gray-900 border border-gray-800 text-gray-500 hover:text-gray-300 hover:border-gray-600 transition-colors disabled:opacity-40"
        title="새로고침"
      >
        <svg
          className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
      {TICKER_CONFIG.map(({ key, label, unit, fmt, fmtChange }) => {
        const item = data?.[key as keyof MacroData] as IndicatorData | undefined;
        const isPos = (item?.change ?? 0) > 0;
        const isNeg = (item?.change ?? 0) < 0;
        const upColor   = key === 'krwUsd' ? 'text-red-400'   : 'text-green-400';
        const downColor = key === 'krwUsd' ? 'text-green-400' : 'text-red-400';

        return (
          <div
            key={key}
            className="flex flex-col items-center px-3 py-1 rounded-lg bg-gray-900 border border-gray-800 min-w-[72px]"
          >
            <span className="text-gray-500 text-[10px] font-medium leading-tight">{label}</span>
            {isLoading || !item || item.price === 0 ? (
              <div className="h-3.5 w-12 bg-gray-800 rounded animate-pulse mt-0.5" />
            ) : (
              <>
                <div className="flex items-baseline gap-0.5">
                  <span className="text-white text-xs font-semibold tabular-nums">
                    {fmt(item.price)}
                  </span>
                  {unit && <span className="text-gray-500 text-[9px]">{unit}</span>}
                </div>
                {!item.isStatic && (isPos || isNeg) ? (
                  <div className={`flex items-center gap-0.5 text-[9px] tabular-nums ${isPos ? upColor : downColor}`}>
                    <span>{isPos ? '▲' : '▼'}</span>
                    <span>{fmtChange(item.change)}</span>
                    <span className="opacity-60">({isPos ? '+' : ''}{item.changePct.toFixed(2)}%)</span>
                  </div>
                ) : (
                  <div className="text-[9px] text-gray-700">전일 동일</div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
