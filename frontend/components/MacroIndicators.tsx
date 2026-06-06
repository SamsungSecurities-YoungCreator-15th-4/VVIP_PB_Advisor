'use client';

import { useState, useEffect } from 'react';

interface IndicatorData {
  price: number;
  change: number;
  changePct: number;
  isStatic?: boolean;
}

interface MacroShock {
  baseRateDelta: number;
  krwUsdDelta: number;
}

interface Props {
  onShockChange?: (shock: MacroShock) => void;
}

export default function MacroIndicators({ onShockChange }: Props) {
  const [liveBase, setLiveBase] = useState(2.75);
  const [liveKrwUsd, setLiveKrwUsd] = useState(1531);
  const [baseRateVal, setBaseRateVal] = useState(2.75);
  const [krwUsdVal, setKrwUsdVal] = useState(1531);
  const [loaded, setLoaded] = useState(false);

  // 헤더 ticker가 이미 fetch하므로 cache hit으로 빠르게 응답됨
  useEffect(() => {
    fetch('/api/macro-indicators')
      .then(r => r.json())
      .then((d: { baseRate: IndicatorData; krwUsd: IndicatorData }) => {
        const base = d.baseRate?.price ?? 2.75;
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
    onShockChange?.({ baseRateDelta, krwUsdDelta });
  }, [baseRateVal, krwUsdVal, liveBase, liveKrwUsd, onShockChange]);

  const hasShock =
    Math.abs(baseRateVal - liveBase) > 0.04 ||
    Math.abs(krwUsdVal - liveKrwUsd) > 4;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
          스트레스 시나리오 조율기
        </span>
        <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded">D</span>
      </div>

      {/* 기준금리 슬라이더 (0.0 ~ 6.0%) */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400">기준금리</span>
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
        </div>
      )}
    </div>
  );
}
