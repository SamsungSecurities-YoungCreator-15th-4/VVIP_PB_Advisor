/**
 * PB용 PDF 템플릿 — A4 세로(794×1123px) 고정 레이아웃.
 * modern-screenshot 으로 캡처 후 jspdf 로 추출한다.
 * 이 컴포넌트는 화면에 직접 노출되지 않는다(off-screen 렌더링).
 */

import { CUSTOMERS, PORTFOLIOS, TAX_EFFECT, TAX_ADVICE, INSIGHT, BACKTEST_SERIES } from "@/lib/mockData";

const selectedCustomer = CUSTOMERS[0];
const current = PORTFOLIOS.find((p) => p.id === "current")!;
const portA = PORTFOLIOS.find((p) => p.id === "a")!;
const portB = PORTFOLIOS.find((p) => p.id === "b")!;

function MetricRow({ label, current, a, b }: { label: string; current: string; a: string; b: string }) {
  return (
    <tr className="border-b border-gray-100">
      <td className="py-1 pr-3 text-[10px] font-semibold text-gray-500">{label}</td>
      <td className="py-1 px-2 text-center text-[10px] font-bold text-gray-700">{current}</td>
      <td className="py-1 px-2 text-center text-[10px] font-bold text-[#0050D6]">{a}</td>
      <td className="py-1 px-2 text-center text-[10px] font-bold text-[#0050D6]">{b}</td>
    </tr>
  );
}

function SectionTitle({ num, title }: { num: number; title: string }) {
  return (
    <div className="mb-2 flex items-center gap-1.5">
      <span className="flex size-4 items-center justify-center rounded-full bg-[#0050D6]/10 text-[9px] font-extrabold text-[#0050D6]">
        {num}
      </span>
      <span className="text-[11px] font-extrabold text-gray-800">{title}</span>
    </div>
  );
}

export default function PbPdfTemplate() {
  const today = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });

  return (
    <div
      style={{ width: 794, minHeight: 1123, fontFamily: "Pretendard, sans-serif" }}
      className="bg-white p-10"
    >
      {/* ── 헤더 ── */}
      <div className="mb-6 flex items-start justify-between border-b-2 border-[#0050D6] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-[#0050D6] text-sm font-extrabold text-white">
              S
            </div>
            <span className="text-[18px] font-extrabold text-gray-900">S.upervisor</span>
            <span className="ml-1 rounded bg-[#0050D6]/10 px-2 py-0.5 text-[9px] font-bold text-[#0050D6]">
              PB 전용
            </span>
          </div>
          <p className="mt-1 text-[10px] text-gray-400">삼성증권 VVIP 자산관리 상담 리포트</p>
        </div>
        <div className="text-right">
          <p className="text-[11px] font-bold text-gray-700">{selectedCustomer.name} 고객</p>
          <p className="text-[10px] text-gray-400">{selectedCustomer.grade} · {selectedCustomer.aumLabel}</p>
          <p className="mt-1 text-[9px] text-gray-400">담당 PB: {selectedCustomer.pbCode}</p>
          <p className="text-[9px] text-gray-400">작성일: {today}</p>
        </div>
      </div>

      {/* ── 1. 포트폴리오 비교 ── */}
      <div className="mb-5">
        <SectionTitle num={1} title="포트폴리오 성과 비교" />
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              <th className="py-1.5 pr-3 text-left text-[10px] font-extrabold text-gray-500">지표</th>
              <th className="py-1.5 px-2 text-center text-[10px] font-extrabold text-gray-600">현재</th>
              <th className="py-1.5 px-2 text-center text-[10px] font-extrabold text-[#0050D6]">
                포트폴리오 A <span className="text-[8px] font-semibold">(베스트)</span>
              </th>
              <th className="py-1.5 px-2 text-center text-[10px] font-extrabold text-[#0050D6]">
                포트폴리오 B <span className="text-[8px] font-semibold">(추천)</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <MetricRow
              label="기대수익률"
              current={`${current.metrics.expectedReturnPct}%`}
              a={`${portA.metrics.expectedReturnPct}%`}
              b={`${portB.metrics.expectedReturnPct}%`}
            />
            <MetricRow
              label="세후 수익률"
              current={`${current.metrics.afterTaxReturnPct}%`}
              a={`${portA.metrics.afterTaxReturnPct}%`}
              b={`${portB.metrics.afterTaxReturnPct}%`}
            />
            <MetricRow
              label="변동성"
              current={`${current.metrics.volatilityPct}%`}
              a={`${portA.metrics.volatilityPct}%`}
              b={`${portB.metrics.volatilityPct}%`}
            />
            <MetricRow
              label="샤프지수"
              current={`${current.metrics.sharpe}`}
              a={`${portA.metrics.sharpe}`}
              b={`${portB.metrics.sharpe}`}
            />
            <MetricRow
              label="소르티노"
              current={`${current.metrics.sortino}`}
              a={`${portA.metrics.sortino}`}
              b={`${portB.metrics.sortino}`}
            />
            <MetricRow
              label="MDD"
              current={`▼${current.metrics.mddPct}%`}
              a={`▼${portA.metrics.mddPct}%`}
              b={`▼${portB.metrics.mddPct}%`}
            />
            <MetricRow
              label="세후 기대수익"
              current={current.metrics.afterTaxAmountLabel}
              a={portA.metrics.afterTaxAmountLabel}
              b={portB.metrics.afterTaxAmountLabel}
            />
          </tbody>
        </table>
      </div>

      {/* ── 2. 백테스트 요약 ── */}
      <div className="mb-5">
        <SectionTitle num={2} title="백테스트 수익률 추이 (2021–2026, 100 기준)" />
        <div className="flex gap-1 overflow-hidden rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
          {BACKTEST_SERIES.map((row) => (
            <div key={row.year} className="flex-1 text-center">
              <p className="text-[9px] font-semibold text-gray-400">{row.year}</p>
              <p className="text-[10px] font-bold text-gray-600">{row.current}</p>
              <p className="text-[10px] font-bold text-[#0050D6]">{row.a}</p>
              <p className="text-[10px] font-bold text-[#5B9BFF]">{row.b}</p>
            </div>
          ))}
          <div className="flex flex-col justify-center gap-1 pl-3">
            <span className="text-[9px] font-semibold text-gray-500">■ 현재</span>
            <span className="text-[9px] font-semibold text-[#0050D6]">■ A</span>
            <span className="text-[9px] font-semibold text-[#5B9BFF]">■ B</span>
          </div>
        </div>
      </div>

      {/* ── 3. 절세 최적화 ── */}
      <div className="mb-5">
        <SectionTitle num={3} title="절세 최적화 분석" />
        <div className="mb-2 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-2.5 text-center">
            <p className="text-[9px] text-gray-400">세후 수익률 개선</p>
            <p className="text-[13px] font-extrabold text-[#0050D6]">
              {TAX_EFFECT.afterTaxReturn.from} → {TAX_EFFECT.afterTaxReturn.to}
            </p>
            <p className="text-[9px] font-bold text-[#0050D6]">{TAX_EFFECT.afterTaxReturn.delta}</p>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-2.5 text-center">
            <p className="text-[9px] text-gray-400">실효 세금 절감</p>
            <p className="text-[13px] font-extrabold text-[#F04452]">
              {TAX_EFFECT.effectiveTax.delta}
            </p>
            <p className="text-[9px] font-bold text-gray-500">연간</p>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-2.5 text-center">
            <p className="text-[9px] text-gray-400">알고리즘 추가 절감</p>
            <p className="text-[13px] font-extrabold text-[#F04452]">{TAX_ADVICE.totalSaving}</p>
            <p className="text-[9px] font-bold text-gray-500">적용 시 예상</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {TAX_ADVICE.cards.map((c) => (
            <div key={c.title} className="rounded-md border border-gray-100 bg-white p-2">
              <div className="mb-0.5 flex items-center justify-between">
                <span className="text-[10px] font-extrabold text-gray-800">{c.title}</span>
                <span className="text-[10px] font-extrabold text-[#F04452]">{c.saving}</span>
              </div>
              <p className="text-[9px] leading-snug text-gray-500">{c.body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── 4. AI 인사이트 요약 ── */}
      <div className="mb-4">
        <SectionTitle num={4} title="AI 인사이트 요약" />
        <div className="rounded-lg border border-[#0050D6]/15 bg-[#0050D6]/5 p-3">
          <p className="text-[10px] leading-relaxed text-gray-700">
            {INSIGHT.defaultAnswer.split("\n\n")[0]}
          </p>
        </div>
      </div>

      {/* ── 푸터 ── */}
      <div className="mt-4 border-t border-gray-100 pt-3 text-center">
        <p className="text-[8px] text-gray-400">
          본 자료는 삼성증권 S.upervisor 시스템이 생성한 PB 전용 참고자료로, 투자 권유 또는 법적 의견이 아닙니다.
          투자 결정 시 담당 PB의 최종 검토를 거치시기 바랍니다.
        </p>
      </div>
    </div>
  );
}
