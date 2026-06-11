'use client';

// 시나리오 Test 카드 — 목업(vvip_pb_advisor_mockup.html) 우측 컬럼 디자인 기준 (라이트 테마).
// 슬라이더(금리 0~6% / 환율 1,000~2,000원) 절대값을 현재 시세와의 델타로 변환해
// onShockChange로 전달하고, 부모가 계산한 포트폴리오별 예상 평가손익을 표시한다.
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

export default function MacroIndicators({ onShockChange, pnl, pnlLoading }: Props) {
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

  const rateShocked = Math.abs(baseRateVal - liveBase) > 0.04;
  const fxShocked = Math.abs(krwUsdVal - liveKrwUsd) > 4;

  // 충격계수 캘리브레이션 기준점(±100bp/±200원)의 2배 초과 시 선형 외삽 오차가
  // 커지는 구간 — 고객친화 안내 문구를 표시한다 (±200bp/±400원).
  const isExtrapolated =
    Math.abs(baseRateVal - liveBase) > 2.0 ||
    Math.abs(krwUsdVal - liveKrwUsd) > 400;

  // 국내 금융 관례: 상승(+) = 빨강, 하락(−) = 파랑 / 무변동 = 파랑(강조)
  const rateColor = rateShocked
    ? (baseRateVal > liveBase ? 'text-[#F04452]' : 'text-[#3182F6]')
    : 'text-[#0050D6]';
  const fxColor = fxShocked
    ? (krwUsdVal > liveKrwUsd ? 'text-[#F04452]' : 'text-[#3182F6]')
    : 'text-[#0050D6]';

  return (
    <div className="bg-white border border-[#E8EBED] rounded-2xl shadow-sm p-4">
      <div className="text-[13px] font-bold text-[#171C24] mb-3.5">시나리오 Test</div>

      {/* 금리 슬라이더 (0.0 ~ 6.0%) */}
      <div className="mb-4">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] font-bold text-[#4E5968]">금리</span>
          <span className={`text-sm font-extrabold tabular-nums ${rateColor}`}>
            {baseRateVal.toFixed(2)}%
            {rateShocked && (
              <span className="ml-1 text-[10px] font-bold">
                ({baseRateVal > liveBase ? '+' : ''}{(baseRateVal - liveBase).toFixed(2)}%p)
              </span>
            )}
          </span>
        </div>
        <input
          type="range" min={0.0} max={6.0} step={0.25}
          value={baseRateVal}
          onChange={e => setBaseRateVal(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-[#E8EBED] accent-[#0064FF] cursor-pointer"
        />
        <div className="flex justify-between text-[9px] font-semibold text-[#B0B8C1] mt-1">
          <span>0.0%</span>
          <button
            onClick={() => setBaseRateVal(liveBase)}
            className="text-[#8B95A1] hover:text-[#4E5968] transition-colors font-semibold"
          >
            초기화{loaded ? ` (현재 ${liveBase.toFixed(2)}%)` : ''}
          </button>
          <span>6.0%</span>
        </div>
      </div>

      {/* 환율 슬라이더 (1,000 ~ 2,000원) */}
      <div className="mb-4">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] font-bold text-[#4E5968]">환율</span>
          <span className={`text-sm font-extrabold tabular-nums ${fxColor}`}>
            {krwUsdVal.toLocaleString()}원
            {fxShocked && (
              <span className="ml-1 text-[10px] font-bold">
                ({krwUsdVal > liveKrwUsd ? '+' : ''}{(krwUsdVal - liveKrwUsd).toLocaleString()}원)
              </span>
            )}
          </span>
        </div>
        <input
          type="range" min={1000} max={2000} step={10}
          value={krwUsdVal}
          onChange={e => setKrwUsdVal(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-[#E8EBED] accent-[#0064FF] cursor-pointer"
        />
        <div className="flex justify-between text-[9px] font-semibold text-[#B0B8C1] mt-1">
          <span>1,000</span>
          <button
            onClick={() => setKrwUsdVal(liveKrwUsd)}
            className="text-[#8B95A1] hover:text-[#4E5968] transition-colors font-semibold"
          >
            초기화{loaded ? ` (현재 ${liveKrwUsd.toLocaleString()}원)` : ''}
          </button>
          <span>2,000</span>
        </div>
      </div>

      {/* 예상 평가손익 — 목업 scn-pnl 스타일 */}
      {pnl && pnl.length > 0 && (
        <div className="bg-[#EEF4FF] rounded-[10px] px-3.5 py-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-[#4E5968]">예상 평가손익 (연간)</span>
            {pnlLoading && <span className="text-[10px] font-semibold text-[#8B95A1]">재계산 중…</span>}
          </div>
          <div className="space-y-1">
            {pnl.map(row => {
              const man = Math.round(row.eok * 10000);
              const color = man === 0 ? 'text-[#8B95A1]' : man > 0 ? 'text-[#F04452]' : 'text-[#3182F6]';
              return (
                <div key={row.id} className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-[#4E5968]">{row.label}</span>
                  <span className={`text-[13px] font-extrabold tabular-nums ${color}`}>{fmtPnl(row.eok)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 급변 시나리오 안내 — 목업 scn-note 스타일 (외삽 구간에서만 표시) */}
      {isExtrapolated && (
        <div className="mt-2 flex gap-1.5 items-start bg-[#EEF4FF] rounded-[9px] px-2.5 py-2">
          <span className="text-[11px] leading-snug">💡</span>
          <span className="text-[10px] font-medium leading-relaxed text-[#4E5968]">
            매우 큰 폭의 변동을 가정한 시나리오입니다. 정밀한 수치보다는 전체적인 흐름을
            보시는 용도로 적합합니다.
          </span>
        </div>
      )}
    </div>
  );
}
