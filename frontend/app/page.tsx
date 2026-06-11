'use client';

// 메인 대시보드 — 목업(vvip_pb_advisor_mockup.html) 구조 기준.
// 우측 "시나리오 Test" 조절기(금리 0~6% / 환율 1,000~2,000원)를 움직이면
// /api/stressed-portfolios를 재호출해 중앙의 현재·A·B 포트폴리오 카드 지표와
// 예상 평가손익이 함께 갱신된다. 고정 시나리오 막대·과거 위기 패널은
// 대시보드에서 제외 (API는 유지 — 제안서 PDF 등에서 재사용 가능).
import { useEffect, useState } from 'react';

import MacroIndicators, { type PnlRow } from '@/components/MacroIndicators';
import { fetchPortfolios, fetchStressedPortfolios } from '@/lib/api';
import type { PortfolioProposal, StressedPortfolio } from '@/lib/types';

interface MacroShock {
  baseRateDelta: number; // bp
  krwUsdDelta: number; // 원
}

// 고객 운용자산 (억 원) — 고객 상세(/clients/:id) 연동 전 목업 기준 상수
const TOTAL_ASSETS_EOK = 18;

const PORTFOLIO_LABELS: Record<string, string> = {
  current: '현재',
  proposalA: '제안 A',
  proposalB: '제안 B',
};

const PORTFOLIO_TITLE_COLORS: Record<string, string> = {
  current: 'text-[#4E5968]',
  proposalA: 'text-[#0064FF]',
  proposalB: 'text-[#7C5CFF]',
};

type MetricKey = 'expectedReturn' | 'volatility' | 'sharpeRatio' | 'sortinoRatio' | 'maxDrawdown';

const METRIC_DEFS: { key: MetricKey; label: string; isPct: boolean }[] = [
  { key: 'expectedReturn', label: '기대수익률', isPct: true },
  { key: 'volatility', label: '변동성', isPct: true },
  { key: 'sharpeRatio', label: '샤프지수', isPct: false },
  { key: 'sortinoRatio', label: '소르티노', isPct: false },
  { key: 'maxDrawdown', label: 'MDD', isPct: true },
];

function fmt(value: number | null | undefined, isPct: boolean): string {
  if (value === null || value === undefined) return 'N/A';
  return isPct ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
}

function PortfolioCard({
  proposal,
  stressed,
  hasShock,
}: {
  proposal: PortfolioProposal;
  stressed?: StressedPortfolio;
  hasShock: boolean;
}) {
  const base = stressed?.base ?? proposal.metrics;
  const shown = hasShock && stressed ? stressed.stressed : base;
  if (!base || !shown) return null;

  return (
    <div className="bg-white rounded-2xl p-4 border border-[#E8EBED] shadow-sm">
      <div className={`text-[13px] font-extrabold mb-0.5 ${PORTFOLIO_TITLE_COLORS[proposal.id]}`}>
        {proposal.nameKr}
      </div>
      <div className="text-[10px] font-semibold text-[#8B95A1] mb-3">{proposal.theme}</div>
      <div className="divide-y divide-[#F1F3F5]">
        {METRIC_DEFS.map(def => {
          const b = base[def.key] as number | null;
          const s = shown[def.key] as number | null;
          const delta = b !== null && s !== null && b !== undefined && s !== undefined ? s - b : null;
          const isZero = delta === null || Math.abs(delta) < (def.isPct ? 0.0005 : 0.005);
          // 국내 금융 관례: 상승(+) = 빨강, 하락(−) = 파랑
          const deltaColor = isZero
            ? 'text-[#B0B8C1]'
            : (delta as number) > 0 ? 'text-[#F04452]' : 'text-[#3182F6]';
          return (
            <div key={def.key} className="flex items-center justify-between py-1.5 text-xs">
              <span className="font-semibold text-[#8B95A1]">{def.label}</span>
              <span className="tabular-nums flex items-center gap-1.5">
                <span className="font-extrabold text-[#171C24]">{fmt(s, def.isPct)}</span>
                {hasShock && !isZero && delta !== null && (
                  <span className={`text-[10px] font-bold ${deltaColor}`}>
                    ({delta > 0 ? '+' : ''}
                    {def.isPct ? `${(delta * 100).toFixed(1)}%p` : delta.toFixed(2)})
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Home() {
  const [portfolios, setPortfolios] = useState<PortfolioProposal[]>([]);
  const [shock, setShock] = useState<MacroShock>({ baseRateDelta: 0, krwUsdDelta: 0 });
  // 응답이 어떤 충격값(key)에 대한 것인지 함께 저장 — 로딩/표시 여부는 key 비교로 파생
  const [stressResult, setStressResult] = useState<{
    key: string;
    data: StressedPortfolio[] | null;
  } | null>(null);
  const [error, setError] = useState(false);

  const hasShock = Math.abs(shock.baseRateDelta) >= 1 || Math.abs(shock.krwUsdDelta) >= 1;
  const shockKey = `${shock.baseRateDelta}:${shock.krwUsdDelta}`;

  useEffect(() => {
    fetchPortfolios()
      .then(setPortfolios)
      .catch(() => setError(true));
  }, []);

  // 슬라이더 변경 시 스트레스 재계산 (드래그 중 과도한 호출 방지 — 400ms 디바운스)
  useEffect(() => {
    if (!hasShock) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchStressedPortfolios(shock.baseRateDelta, shock.krwUsdDelta)
        .then(data => {
          if (!cancelled) setStressResult({ key: shockKey, data });
        })
        .catch(() => {
          if (!cancelled) setStressResult({ key: shockKey, data: null });
        });
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [shockKey, hasShock, shock.baseRateDelta, shock.krwUsdDelta]);

  // 현재 충격값에 대한 응답일 때만 사용 — 아니면 로딩 중으로 파생
  const stressedData = hasShock && stressResult?.key === shockKey ? stressResult.data : null;
  const stressLoading = hasShock && stressResult?.key !== shockKey;

  // 예상 평가손익 = (충격 후 기대수익률 − 기준 기대수익률) × 운용자산
  const pnl: PnlRow[] = portfolios.map(p => {
    const s = stressedData?.find(x => x.id === p.id);
    const delta = hasShock && s ? s.stressed.expectedReturn - s.base.expectedReturn : 0;
    return { id: p.id, label: PORTFOLIO_LABELS[p.id] ?? p.nameKr, eok: delta * TOTAL_ASSETS_EOK };
  });

  return (
    <main className="min-h-screen bg-[#EDEFF2] text-[#171C24]">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-5">
        <header className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-[9px] bg-gradient-to-br from-[#2C7BFF] to-[#0050D6] flex items-center justify-center text-white font-extrabold text-lg">
            V
          </div>
          <div>
            <h1 className="text-[15px] font-extrabold tracking-tight">VVIP PB Advisor</h1>
            <p className="text-[9px] font-bold text-[#8B95A1] tracking-[0.12em]">PORTFOLIO ADVISORY</p>
          </div>
        </header>

        {error && (
          <div className="bg-[#FEECEE] border border-[#FBD5D9] rounded-xl p-4 text-sm font-semibold text-[#F04452]">
            백엔드에 연결할 수 없습니다 — uvicorn(localhost:8000)이 켜져 있는지 확인하세요.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4 items-start">
          {/* 중앙: 포트폴리오 카드 — 조절기 충격 반영 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {portfolios.map(p => (
              <PortfolioCard
                key={p.id}
                proposal={p}
                stressed={stressedData?.find(x => x.id === p.id)}
                hasShock={hasShock && !!stressedData}
              />
            ))}
          </div>

          {/* 우측: 시나리오 Test (조절기 + 예상 평가손익) */}
          <MacroIndicators onShockChange={setShock} pnl={pnl} pnlLoading={stressLoading} />
        </div>
      </div>
    </main>
  );
}
