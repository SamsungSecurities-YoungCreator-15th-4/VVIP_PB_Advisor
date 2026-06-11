'use client';

import { useState, useEffect, useRef } from 'react';
import { fetchMacroIndicators } from '@/lib/api';

interface MacroShock {
  baseRateDelta: number;
  krwUsdDelta: number;
}

/** 포트폴리오별 예상 평가손익 (연간, 억 원 단위) */
export interface PnlRow {
  id: string;
  label: string;
  eok: number;
}

interface Props {
  onShockChange?: (shock: MacroShock) => void;
  /** 시나리오 적용 시 포트폴리오별 예상 평가손익 — 전달되면 슬라이더 아래 표시 */
  pnl?: PnlRow[];
  /** 평가손익 기준 운용자산 (억 원) */
  totalAssetsEok?: number;
  /** 스트레스 재계산 중 여부 */
  pnlLoading?: boolean;
}

function fmtPnl(eok: number): string {
  const man = Math.round(eok * 10000);
  if (man === 0) return '0만원';
  const sign = man > 0 ? '▲ ' : '▼ ';
  const abs = Math.abs(man);
  return sign + (abs >= 10000 ? `${(abs / 10000).toFixed(1)}억원` : `${abs.toLocaleString()}만원`);
}

export default function MacroIndicators({ onShockChange, pnl, totalAssetsEok, pnlLoading }: Props) {
  const [liveBase, setLiveBase] = useState(3.75);
  const [liveKrwUsd, setLiveKrwUsd] = useState(1531);
  const [baseRateVal, setBaseRateVal] = useState(3.75);
  const [krwUsdVal, setKrwUsdVal] = useState(1531);
  const [loaded, setLoaded] = useState(false);

  // 부모가 onShockChange를 메모이제이션하지 않아도 무한 루프 방지
  const onShockChangeRef = useRef(onShockChange);
  useEffect(() => { onShockChangeRef.current = onShockChange; });

  // 헤더 ticker가 이미 fetch하므로 백엔드 캐시 hit으로 빠르게 응답됨
  useEffect(() => {
    fetchMacroIndicators()
      .then((d) => {
        const base = d.baseRate?.price ?? 3.75;
        const fx = d.krwUsd?.price ?? 1531;
        setLiveBase(base);
        setLiveKrwUsd(Math.round(fx));
        setBaseRateVal(base);
        setKrwUsdVal(Math.round(fx));
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  useEffect(() => {
    const baseRateDelta = Math.round((baseRateVal - liveBase) * 100);
    const krwUsdDelta = krwUsdVal - liveKrwUsd;
    onShockChangeRef.current?.({ baseRateDelta, krwUsdDelta });
  }, [baseRateVal, krwUsdVal, liveBase, liveKrwUsd]);

  const hasShock =
    Math.abs(baseRateVal - liveBase) > 0.04 ||
    Math.abs(krwUsdVal - liveKrwUsd) > 4;

  // 충격계수 캘리브레이션 기준점(±100bp/±200원)의 2배 초과 시 선형 외삽 오차가
  // 커지는 구간 — StressTest의 TunerImpactPanel 배지와 동일 기준(±200bp/±400원).
  const isExtrapolated =
    Math.abs(baseRateVal - liveBase) > 2.0 ||
    Math.abs(krwUsdVal - liveKrwUsd) > 400;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
          스트레스 시나리오 조율기
        </span>
        <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded">D</span>
      </div>

      {/* 美 기준금리 슬라이더 (0.0 ~ 6.0%) */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400">美 기준금리</span>
          <div className="flex items-center gap-2">
            {loaded && (
              <span className="text-[10px] text-gray-600">현재 {liveBase.toFixed(2)}%</span>
            )}
            <span className={`text-xs font-semibold tabular-nums ${hasShock && Math.abs(baseRateVal - liveBase) > 0.04
              ? baseRateVal > liveBase ? 'text-red-400' : 'text-green-400'
              : 'text-gray-200'
              }`}>
              {baseRateVal.toFixed(2)}%
            </span>
          </div>
        </div>
        <input
          type="range" min={0.0} max={6.0} step={0.25}
          value={baseRateVal}
          onChange={e => setBaseRateVal(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-gray-700 accent-blue-500 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-gray-600 mt-1">
          <span>0.0%</span>
          <button
            onClick={() => setBaseRateVal(liveBase)}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            초기화
          </button>
          <span>6.0%</span>
        </div>
      </div>

      {/* 원/달러 슬라이더 (1,000 ~ 2,000원) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400">원/달러 환율</span>
          <div className="flex items-center gap-2">
            {loaded && (
              <span className="text-[10px] text-gray-600">현재 {liveKrwUsd.toLocaleString()}원</span>
            )}
            <span className={`text-xs font-semibold tabular-nums ${hasShock && Math.abs(krwUsdVal - liveKrwUsd) > 4
              ? krwUsdVal > liveKrwUsd ? 'text-red-400' : 'text-green-400'
              : 'text-gray-200'
              }`}>
              {krwUsdVal.toLocaleString()}원
            </span>
          </div>
        </div>
        <input
          type="range" min={1000} max={2000} step={10}
          value={krwUsdVal}
          onChange={e => setKrwUsdVal(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-gray-700 accent-purple-500 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-gray-600 mt-1">
          <span>1,000</span>
          <button
            onClick={() => setKrwUsdVal(liveKrwUsd)}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            초기화
          </button>
          <span>2,000</span>
        </div>
      </div>

      {pnl && pnl.length > 0 && (
        <div className="mt-4 bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-gray-300 font-medium">
              예상 평가손익{totalAssetsEok ? ` (${totalAssetsEok}억 기준 · 연간)` : ''}
            </span>
            {pnlLoading && <span className="text-[10px] text-yellow-400">재계산 중…</span>}
          </div>
          <div className="space-y-1">
            {pnl.map(row => {
              const man = Math.round(row.eok * 10000);
              const color = man === 0 ? 'text-gray-400' : man > 0 ? 'text-green-400' : 'text-red-400';
              return (
                <div key={row.id} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{row.label}</span>
                  <span className={`font-semibold tabular-nums ${color}`}>{fmtPnl(row.eok)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {hasShock && (
        <div className="mt-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2.5">
          <div className="text-xs text-yellow-400 font-medium mb-1">⚡ 시나리오 적용 중</div>
          <div className="text-xs text-gray-400 space-y-0.5">
            <div>
              금리: {liveBase.toFixed(2)}% → <span className="text-yellow-300 font-medium">{baseRateVal.toFixed(2)}%</span>
              <span className={`ml-1 ${baseRateVal > liveBase ? 'text-red-400' : 'text-green-400'}`}>
                ({baseRateVal > liveBase ? '+' : ''}{(baseRateVal - liveBase).toFixed(2)}%p)
              </span>
            </div>
            <div>
              환율: {liveKrwUsd.toLocaleString()}원 → <span className="text-yellow-300 font-medium">{krwUsdVal.toLocaleString()}원</span>
              <span className={`ml-1 ${krwUsdVal > liveKrwUsd ? 'text-red-400' : 'text-green-400'}`}>
                ({krwUsdVal > liveKrwUsd ? '+' : ''}{(krwUsdVal - liveKrwUsd).toLocaleString()}원)
              </span>
            </div>
          </div>
          {isExtrapolated && (
            <div className="mt-2 pt-2 border-t border-yellow-500/20 text-[11px] text-yellow-400/90">
              💡 매우 큰 폭의 변동을 가정한 시나리오입니다. 정밀한 수치보다는
              전체적인 흐름을 보시는 용도로 적합합니다.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
