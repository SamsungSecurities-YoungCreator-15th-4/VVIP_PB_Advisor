/**
 * 고객용 PDF 템플릿 — A4 세로(794×1123px) 고정 레이아웃.
 * PB용과 달리 전문 지표(샤프·소르티노 등)는 제외하고
 * 고객이 직관적으로 이해할 수 있는 핵심 정보만 담는다.
 */

import { CUSTOMERS, PORTFOLIOS, TAX_EFFECT, TAX_ADVICE } from "@/lib/mockData";

const selectedCustomer = CUSTOMERS[0];
const portA = PORTFOLIOS.find((p) => p.id === "a")!;

function HighlightCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border bg-white p-4 text-center shadow-sm">
      <p className="mb-1 text-[10px] font-semibold text-gray-400">{label}</p>
      <p className={`text-[20px] font-extrabold ${color}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[9px] font-semibold text-gray-400">{sub}</p>}
    </div>
  );
}

function TaxCard({ icon, title, saving, body }: { icon: string; title: string; saving: string; body: string }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-[#F8FAFF] p-3">
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="flex size-5 items-center justify-center rounded-full bg-[#0050D6]/10 text-[10px] font-extrabold text-[#0050D6]">
            {icon}
          </span>
          <span className="text-[11px] font-extrabold text-gray-800">{title}</span>
        </div>
        <span className="text-[11px] font-extrabold text-[#F04452]">{saving}</span>
      </div>
      <p className="text-[9px] leading-snug text-gray-500">{body}</p>
    </div>
  );
}

export default function ClientPdfTemplate() {
  const today = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });

  return (
    <div
      style={{ width: 794, minHeight: 1123, fontFamily: "Pretendard, sans-serif" }}
      className="bg-white p-10"
    >
      {/* ── 헤더 ── */}
      <div className="mb-7 flex items-start justify-between border-b-2 border-[#0050D6] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-[#0050D6] text-sm font-extrabold text-white">
              S
            </div>
            <span className="text-[18px] font-extrabold text-gray-900">S.upervisor</span>
          </div>
          <p className="mt-1 text-[10px] text-gray-400">삼성증권 VVIP 자산관리 상담 리포트</p>
        </div>
        <div className="text-right">
          <p className="text-[13px] font-extrabold text-gray-800">{selectedCustomer.name} 고객님</p>
          <p className="text-[10px] text-gray-400">{selectedCustomer.aumLabel}</p>
          <p className="mt-1 text-[9px] text-gray-400">작성일: {today}</p>
        </div>
      </div>

      {/* ── 인사말 ── */}
      <div className="mb-7 rounded-xl bg-[#F0F5FF] p-4">
        <p className="text-[11px] leading-relaxed text-gray-700">
          안녕하세요, <strong>{selectedCustomer.name}</strong> 고객님. 오늘 상담에서 논의한
          내용을 바탕으로 고객님께 최적화된 포트폴리오 제안과 절세 전략을 정리해 드립니다.
          궁금하신 점은 담당 PB에게 언제든지 문의해 주세요.
        </p>
      </div>

      {/* ── 1. 추천 포트폴리오 핵심 지표 ── */}
      <div className="mb-7">
        <h2 className="mb-3 flex items-center gap-2 text-[13px] font-extrabold text-gray-800">
          <span className="flex size-5 items-center justify-center rounded-full bg-[#0050D6] text-[9px] font-extrabold text-white">1</span>
          추천 포트폴리오 핵심 성과
        </h2>
        <p className="mb-3 text-[10px] text-gray-500">
          포트폴리오 A (베스트) 기준 · {selectedCustomer.aumLabel}
        </p>
        <div className="grid grid-cols-3 gap-3">
          <HighlightCard
            label="세후 기대 수익률"
            value={`${portA.metrics.afterTaxReturnPct}%`}
            sub="연간 기준"
            color="text-[#0050D6]"
          />
          <HighlightCard
            label="최대 예상 손실(MDD)"
            value={`▼${portA.metrics.mddPct}%`}
            sub={portA.metrics.mddAmountLabel}
            color="text-[#F04452]"
          />
          <HighlightCard
            label="연간 세후 기대수익"
            value={portA.metrics.afterTaxAmountLabel}
            sub="세금 최적화 적용 시"
            color="text-[#0050D6]"
          />
        </div>
      </div>

      {/* ── 2. 현재 vs 추천 비교 ── */}
      <div className="mb-7">
        <h2 className="mb-3 flex items-center gap-2 text-[13px] font-extrabold text-gray-800">
          <span className="flex size-5 items-center justify-center rounded-full bg-[#0050D6] text-[9px] font-extrabold text-white">2</span>
          현재 포트폴리오 vs 추천 포트폴리오 비교
        </h2>
        <div className="overflow-hidden rounded-xl border border-gray-100">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#F0F5FF]">
                <th className="py-2 pl-4 text-left text-[10px] font-extrabold text-gray-500">항목</th>
                <th className="py-2 px-3 text-center text-[10px] font-extrabold text-gray-600">현재</th>
                <th className="py-2 px-3 text-center text-[10px] font-extrabold text-[#0050D6]">추천 (A)</th>
                <th className="py-2 pr-4 text-center text-[10px] font-extrabold text-[#0050D6]">변화</th>
              </tr>
            </thead>
            <tbody>
              {[
                {
                  label: "세후 수익률",
                  cur: "4.0%",
                  rec: "5.5%",
                  diff: "+1.5%p ▲",
                  diffColor: "text-[#F04452]",
                },
                {
                  label: "기대 수익률",
                  cur: "4.8%",
                  rec: "6.4%",
                  diff: "+1.6%p ▲",
                  diffColor: "text-[#F04452]",
                },
                {
                  label: "최대 예상 손실",
                  cur: "▼14.6%",
                  rec: "▼11.2%",
                  diff: "−3.4%p 개선",
                  diffColor: "text-[#0050D6]",
                },
                {
                  label: "연간 세후 기대수익",
                  cur: "+7,200만원",
                  rec: "+9,900만원",
                  diff: "+2,700만원",
                  diffColor: "text-[#F04452]",
                },
              ].map((row, i) => (
                <tr key={row.label} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                  <td className="py-2 pl-4 text-[10px] font-semibold text-gray-600">{row.label}</td>
                  <td className="py-2 px-3 text-center text-[10px] font-bold text-gray-600">{row.cur}</td>
                  <td className="py-2 px-3 text-center text-[10px] font-bold text-[#0050D6]">{row.rec}</td>
                  <td className={`py-2 pr-4 text-center text-[10px] font-extrabold ${row.diffColor}`}>{row.diff}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── 3. 절세 전략 ── */}
      <div className="mb-7">
        <h2 className="mb-3 flex items-center gap-2 text-[13px] font-extrabold text-gray-800">
          <span className="flex size-5 items-center justify-center rounded-full bg-[#0050D6] text-[9px] font-extrabold text-white">3</span>
          맞춤 절세 전략
        </h2>
        <div className="mb-3 rounded-xl bg-[#FFF5F6] px-4 py-3 text-center">
          <p className="text-[11px] text-gray-600">
            절세 전략 적용 시 예상 연간 절감액
          </p>
          <p className="text-[22px] font-extrabold text-[#F04452]">{TAX_EFFECT.effectiveTax.delta}</p>
          <p className="text-[9px] text-gray-400">{TAX_EFFECT.subNote}</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {TAX_ADVICE.cards.map((c) => (
            <TaxCard key={c.title} icon={c.icon} title={c.title} saving={c.saving} body={c.body} />
          ))}
        </div>
      </div>

      {/* ── 푸터 ── */}
      <div className="mt-auto border-t border-gray-100 pt-4 text-center">
        <p className="text-[8px] leading-relaxed text-gray-400">
          본 자료는 상담 내용을 바탕으로 작성된 참고용 리포트이며, 투자 권유나 법적 조언이 아닙니다.
          투자에는 원금 손실의 위험이 있으며, 과거 성과가 미래 수익을 보장하지 않습니다.
          삼성증권 · 삼성증권 S.upervisor
        </p>
      </div>
    </div>
  );
}
