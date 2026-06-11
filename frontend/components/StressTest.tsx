'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchHistoricalCrises, fetchStressedPortfolios } from '@/lib/api';
import type {
  HistoricalCrisis,
  PortfolioMetrics,
  PortfolioProposal,
  StressedPortfolio,
  StressScenario,
} from '@/lib/types';

// MacroIndicators(조율기)의 onShockChange가 전달하는 값과 동일한 형태
export interface MacroShock {
  baseRateDelta: number; // bp
  krwUsdDelta: number; // 원
}

interface Props {
  scenarios: StressScenario[];
  portfolios: PortfolioProposal[];
  /** 스트레스 조율기 슬라이더 값 — 전달되면 전체 지표(수익률·변동성·샤프·소르티노·MDD)를 재계산해 표시 */
  shock?: MacroShock;
}

const PORTFOLIO_COLORS: Record<string, string> = {
  current: 'text-gray-300',
  proposalA: 'text-blue-400',
  proposalB: 'text-purple-400',
};

function ImpactBar({ value, maxAbs, unit = '%p' }: { value: number; maxAbs: number; unit?: string }) {
  const isZero = Math.abs(value) < 0.0001;
  const isPositive = value > 0;
  const pct = Math.abs(value) / maxAbs * 100;
  const textColor = isZero ? '#6b7280' : isPositive ? '#34d399' : '#f87171';
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 flex justify-end">
        {!isZero && !isPositive && (
          <div
            className="h-4 rounded-l bg-red-500/60 transition-all"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <div className="w-14 text-center text-xs font-medium" style={{ color: textColor }}>
        {isZero ? '0.0' : (value > 0 ? '+' : '') + (value * 100).toFixed(1)}{unit}
      </div>
      <div className="flex-1">
        {!isZero && isPositive && (
          <div
            className="h-4 rounded-r bg-green-500/60 transition-all"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}

// ── 조율기 연동: 전체 지표 비교 ──────────────────────────────────────────────

type MetricKey = 'expectedReturn' | 'volatility' | 'sharpeRatio' | 'sortinoRatio' | 'maxDrawdown';

const METRIC_DEFS: {
  key: MetricKey;
  label: string;
  isPct: boolean;
  higherIsBetter: boolean;
}[] = [
  { key: 'expectedReturn', label: '기대수익률', isPct: true, higherIsBetter: true },
  { key: 'volatility', label: '변동성', isPct: true, higherIsBetter: false },
  { key: 'sharpeRatio', label: '샤프지수', isPct: false, higherIsBetter: true },
  { key: 'sortinoRatio', label: '소르티노', isPct: false, higherIsBetter: true },
  { key: 'maxDrawdown', label: 'MDD', isPct: true, higherIsBetter: false },
];

function fmt(value: number | null, isPct: boolean): string {
  if (value === null || value === undefined) return 'N/A';
  return isPct ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
}

function MetricRow({ def, base, stressed }: {
  def: (typeof METRIC_DEFS)[number];
  base: PortfolioMetrics;
  stressed: PortfolioMetrics;
}) {
  const b = base[def.key];
  const s = stressed[def.key];
  const hasBoth = b !== null && b !== undefined && s !== null && s !== undefined;
  const delta = hasBoth ? (s as number) - (b as number) : null;
  const isZero = delta === null || Math.abs(delta) < (def.isPct ? 0.0005 : 0.005);
  const improved = delta !== null && (def.higherIsBetter ? delta > 0 : delta < 0);
  const deltaColor = isZero ? 'text-gray-500' : improved ? 'text-green-400' : 'text-red-400';

  return (
    <div className="flex items-center justify-between text-xs py-1">
      <span className="text-gray-400 w-20 flex-shrink-0">{def.label}</span>
      <div className="flex items-center gap-1.5 tabular-nums">
        <span className="text-gray-500">{fmt(b as number | null, def.isPct)}</span>
        <span className="text-gray-600">→</span>
        <span className="text-gray-200 font-medium">{fmt(s as number | null, def.isPct)}</span>
        <span className={`w-16 text-right ${deltaColor}`}>
          {delta === null
            ? ''
            : isZero
              ? '—'
              : (delta > 0 ? '+' : '') + (def.isPct ? `${(delta * 100).toFixed(1)}%p` : delta.toFixed(2))}
        </span>
      </div>
    </div>
  );
}

function TunerImpactPanel({ shock }: { shock: MacroShock }) {
  const [data, setData] = useState<StressedPortfolio[] | null>(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 충격계수는 ±100bp/±200원 기준 캘리브레이션 후 선형 비례 적용.
  // 기준점의 2배(±200bp/±400원)를 넘으면 비선형 효과(채권 컨벡시티, 패닉 국면)로
  // 선형 외삽 오차가 점추정 오차를 초과하기 시작하므로 "방향성 참고용"으로 안내한다.
  const isExtrapolated =
    Math.abs(shock.baseRateDelta) > 200 || Math.abs(shock.krwUsdDelta) > 400;

  useEffect(() => {
    // 슬라이더 드래그 중 과도한 호출 방지 (400ms 디바운스)
    if (timerRef.current) clearTimeout(timerRef.current);
    setLoading(true);
    timerRef.current = setTimeout(() => {
      fetchStressedPortfolios(shock.baseRateDelta, shock.krwUsdDelta)
        .then(setData)
        .catch(() => setData(null))
        .finally(() => setLoading(false));
    }, 400);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [shock.baseRateDelta, shock.krwUsdDelta]);

  return (
    <div className="bg-gray-800 rounded-xl p-4 border border-yellow-500/20">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">🎛️</span>
        <div>
          <div className="text-white font-medium text-sm">조율기 시나리오 — 전체 지표 영향</div>
          <div className="text-gray-400 text-xs">
            기준금리 {shock.baseRateDelta >= 0 ? '+' : ''}{shock.baseRateDelta}bp ·
            원/달러 {shock.krwUsdDelta >= 0 ? '+' : ''}{shock.krwUsdDelta.toLocaleString()}원
            {loading && <span className="ml-2 text-yellow-400">재계산 중…</span>}
          </div>
        </div>
        {isExtrapolated && (
          <span
            className="ml-auto flex-shrink-0 text-[10px] text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 rounded px-2 py-1"
            title="매우 큰 폭의 변동을 가정한 시나리오로, 정밀한 수치보다는 전체적인 흐름을 보시는 용도로 적합합니다."
          >
            💡 급변 시나리오 — 참고용 추정치
          </span>
        )}
      </div>

      {data === null && !loading && (
        <div className="text-gray-500 text-xs text-center py-4">
          스트레스 지표를 불러오지 못했습니다
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {data.map(p => (
            <div key={p.id} className="bg-gray-900/60 rounded-lg p-3">
              <div className={`text-xs font-medium mb-2 ${PORTFOLIO_COLORS[p.id]}`}>{p.nameKr}</div>
              <div className="divide-y divide-gray-800">
                {METRIC_DEFS.map(def => (
                  <MetricRow key={def.key} def={def} base={p.base} stressed={p.stressed} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 과거 위기 재현: 실제 수익률 기반 예상 P&L ────────────────────────────────

function HistoricalCrisisPanel({ portfolios }: { portfolios: PortfolioProposal[] }) {
  const [crises, setCrises] = useState<HistoricalCrisis[] | null>(null);

  useEffect(() => {
    fetchHistoricalCrises()
      .then(setCrises)
      .catch(() => setCrises(null));
  }, []);

  if (!crises) return null;

  const maxAbs = Math.max(
    ...crises.flatMap(c => portfolios.map(p => Math.abs(c.results[p.id] ?? 0))),
    0.01,
  );

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-semibold text-gray-300">과거 위기 재현 — 예상 손실률 (P&L)</span>
        <span className="text-[10px] text-gray-500">위기 기간 실제 수익률 적용 · 기간 수익률(연율화 아님)</span>
      </div>
      <div className="space-y-4">
        {crises.map(crisis => (
          <div key={crisis.id} className="bg-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">{crisis.icon}</span>
              <div>
                <div className="text-white font-medium text-sm">
                  {crisis.nameKr}
                  <span className="ml-2 text-gray-500 text-xs font-normal">{crisis.period}</span>
                </div>
                <div className="text-gray-400 text-xs">{crisis.description}</div>
              </div>
            </div>

            <div className="space-y-2">
              {portfolios.map(p => (
                <div key={p.id} className="flex items-center gap-3">
                  <div className={`text-xs w-28 flex-shrink-0 ${PORTFOLIO_COLORS[p.id]}`}>{p.nameKr}</div>
                  <div className="flex-1">
                    <ImpactBar value={crisis.results[p.id] ?? 0} maxAbs={maxAbs} unit="%" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function StressTest({ scenarios, portfolios, shock }: Props) {
  const hasTunerShock =
    !!shock && (Math.abs(shock.baseRateDelta) >= 1 || Math.abs(shock.krwUsdDelta) >= 1);

  if (scenarios.length === 0 || portfolios.every(p => !p.metrics)) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 bg-red-500/20 rounded-lg flex items-center justify-center text-red-400 text-sm font-bold">3</div>
          <h2 className="text-white font-semibold text-lg">거시경제 스트레스 테스트</h2>
        </div>
        <div className="text-gray-500 text-sm text-center py-8">포트폴리오 데이터 로딩 후 스트레스 테스트가 표시됩니다</div>
      </div>
    );
  }

  const allValues = scenarios.flatMap(s =>
    portfolios.map(p => Math.abs(s.results[p.id] ?? 0))
  );
  const maxAbs = Math.max(...allValues, 0.01);

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-8 h-8 bg-red-500/20 rounded-lg flex items-center justify-center text-red-400 text-sm font-bold">3</div>
        <div>
          <h2 className="text-white font-semibold text-lg">거시경제 스트레스 테스트</h2>
          <p className="text-gray-400 text-sm">위기 시나리오 발생 시 포트폴리오 지표 변화</p>
        </div>
      </div>

      {/* 조율기(슬라이더) 충격 적용 시: 5개 지표 전부 재계산해 비교 */}
      {hasTunerShock && shock && (
        <div className="mb-6">
          <TunerImpactPanel shock={shock} />
        </div>
      )}

      <div className="mb-4 flex items-center gap-4 justify-end">
        {portfolios.map(p => (
          <div key={p.id} className="flex items-center gap-1.5">
            <div className={`w-2.5 h-2.5 rounded-full ${
              p.id === 'current' ? 'bg-gray-400' : p.id === 'proposalA' ? 'bg-blue-400' : 'bg-purple-400'
            }`} />
            <span className="text-xs text-gray-400">{p.nameKr}</span>
          </div>
        ))}
      </div>

      <div className="space-y-6">
        {scenarios.map(scenario => (
          <div key={scenario.id} className="bg-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">{scenario.icon}</span>
              <div>
                <div className="text-white font-medium text-sm">{scenario.nameKr}</div>
                <div className="text-gray-400 text-xs">{scenario.description}</div>
              </div>
            </div>

            <div className="space-y-2">
              {portfolios.map(p => (
                <div key={p.id} className="flex items-center gap-3">
                  <div className={`text-xs w-28 flex-shrink-0 ${PORTFOLIO_COLORS[p.id]}`}>{p.nameKr}</div>
                  <div className="flex-1">
                    <ImpactBar value={scenario.results[p.id] ?? 0} maxAbs={maxAbs} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <HistoricalCrisisPanel portfolios={portfolios} />

      <div className="mt-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
        <div className="text-yellow-400 text-xs font-medium mb-1">⚠️ 해석 가이드</div>
        <div className="text-gray-400 text-xs space-y-1">
          <p>
            조율기 패널의 수치는 충격을 실측 주간수익률 시계열에 주입(드리프트 이동 + 변동성 확대)해
            기대수익률·변동성·샤프·소르티노·MDD를 모두 재계산한 결과입니다.
            하단 막대는 고정 시나리오 발생 시 연간 기대수익률 변화량입니다.
          </p>
          <p>
            &quot;과거 위기 재현&quot;의 수치는 각 위기 기간의 자산군별 실제 실현 수익률(원화 환산,
            사후 확정치)을 현재 비중에 적용한 기간 P&amp;L입니다. 동일 위기가 재발해도 같은
            수익률을 보장하지 않으며, 기간 구간 선택에 따라 수치가 달라질 수 있습니다.
          </p>
          <p>이 추정치는 다음 한계를 가진 단순화된 모델입니다.</p>
          <ul className="list-disc list-inside space-y-0.5">
            <li>비선형성 미반영: 실제 가격-요인 관계는 비선형(예: 채권 컨벡시티)이나 선형 충격으로 단순화했습니다. 슬라이더 값이 기준점(±100bp, ±200원)에서 멀어질수록 오차가 커질 수 있습니다.</li>
            <li>자산 간 상관관계 무시: 각 자산군에 독립적으로 충격을 적용해 복합 충격 시 분산·전이 효과는 반영되지 않습니다.</li>
            <li>변동성 확대 계수는 위기 국면 레짐 효과의 선형 근사(점추정 가정)입니다.</li>
            <li>시기의존성: 위기 국면의 상관관계·변동성은 평시와 크게 달라질 수 있어 점추정치 범위를 벗어날 수 있습니다.</li>
            <li>한국 시장 특수성: 환헤지 비율, 거래시간 차이, 외국인 수급 등은 단순 부호/크기로만 반영했습니다.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
