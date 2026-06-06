'use client';

import type { StressScenario, PortfolioProposal } from '@/lib/types';

interface Props {
  scenarios: StressScenario[];
  portfolios: PortfolioProposal[];
}

const PORTFOLIO_COLORS: Record<string, string> = {
  current: 'text-gray-300',
  proposalA: 'text-blue-400',
  proposalB: 'text-purple-400',
};

function ImpactBar({ value, maxAbs }: { value: number; maxAbs: number }) {
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
        {isZero ? '0.0' : (value > 0 ? '+' : '') + (value * 100).toFixed(1)}%p
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

export default function StressTest({ scenarios, portfolios }: Props) {
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
          <p className="text-gray-400 text-sm">3가지 위기 시나리오 발생 시 기대수익률 변화 (포인트)</p>
        </div>
      </div>

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

      <div className="mt-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
        <div className="text-yellow-400 text-xs font-medium mb-1">⚠️ 해석 가이드</div>
        <div className="text-gray-400 text-xs">
          각 수치는 해당 시나리오 발생 시 연간 기대수익률의 변화량입니다. 양수(+)는 오히려 유리한 방향, 음수(-)는 불리한 방향을 의미합니다.
          실제 시장에서는 여러 충격이 복합적으로 발생할 수 있습니다.
        </div>
      </div>
    </div>
  );
}
