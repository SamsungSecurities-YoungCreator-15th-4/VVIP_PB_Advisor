"use client";

import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxGauge from "@/components/tax/TaxGauge";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import { formatManwon, splitManwon } from "@/lib/format";
import { PORTFOLIOS, TAX_ADVICE, TAX_EFFECT } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import type { PortfolioMetrics, TaxAdviceCard } from "@/lib/types";
import {
  BACKEND_PORTFOLIO_ID,
  useStressedPortfolios,
} from "@/lib/useStressedPortfolios";

// 절세 제안 key → 표시 메타. 절감액·이전금액은 백엔드 실계산값을 본문에 끼워 넣는다.
const ADVICE_META: Record<
  TaxAdviceCard["key"],
  { icon: string; title: string; tag: string; body: (c: TaxAdviceCard) => string }
> = {
  isa: {
    icon: "I",
    title: "ISA 계좌 활용",
    tag: "비과세 자산 이전",
    body: (c) =>
      `이자·배당 자산 ${c.transferableManwon.toLocaleString()}만원을 ISA 잔여 한도로 이전 — 비과세 200만 + 초과분 9.9% 분리과세, 종합과세 합산 제외.`,
  },
  pension_credit: {
    icon: "연",
    title: "연금계좌 세액공제",
    tag: "세액공제",
    body: (c) =>
      `연금저축+IRP 잔여 한도 ${c.transferableManwon.toLocaleString()}만원 납입 시 13.2% 세액공제 — 만 55세 이후 연금 수령.`,
  },
  separate_bond: {
    icon: "채",
    title: "분리과세 채권",
    tag: "분리과세 전환",
    body: () =>
      "일반채·저쿠폰채 이자 중 종합과세 구간분을 장기채권 분리과세(33%)로 종결해 한계세율 과세를 회피.",
  },
  low_tax_dividend: {
    icon: "배",
    title: "저율과세 배당주",
    tag: "저율과세 편입",
    body: () =>
      "고배당(해외배당·리츠) 중 종합과세 구간 배당을 저배당·자본이득형으로 조정해 추가과세 회피.",
  },
  overseas_exemption: {
    icon: "공",
    title: "해외주식 양도 250만 공제",
    tag: "기본공제 활용",
    body: () =>
      "해외주식 양도차익을 연 250만원 기본공제 한도까지 실현해 비과세로 차익 확정.",
  },
  tax_loss: {
    icon: "L",
    title: "Tax-loss Harvesting",
    tag: "평가손실 확정",
    body: () =>
      "평가손실을 확정해 해외주식 양도차익과 통산 → 통산액의 양도세(22%)만큼 절감.",
  },
};

const pctStr = (x: number) => `${(x * 100).toFixed(1)}%`;
const ppStr = (x: number) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%p`;
// 실효세율 = (세전 − 세후) / 세전
const effTaxRate = (m: PortfolioMetrics) =>
  m.expectedReturn > 0 && m.afterTaxReturn != null
    ? (m.expectedReturn - m.afterTaxReturn) / m.expectedReturn
    : 0;
// 세액(억) = (세전 − 세후) × 운용자산
const taxEok = (m: PortfolioMetrics, aum: number) =>
  m.afterTaxReturn != null ? (m.expectedReturn - m.afterTaxReturn) * aum : 0;

/** 중앙 하단: 절세 최적화 시뮬레이터 (절세 효과 / 종합과세 임계선 / 절세 제안) */
export default function TaxSection() {
  const { selectedPortfolioId, selectedCustomerId, customers } =
    useDashboardStore();
  const { byId, failed, aumEokwon } = useStressedPortfolios();
  const portfolio = PORTFOLIOS.find((p) => p.id === selectedPortfolioId);
  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const baseLabel = `기준 : ${portfolio?.name ?? "포트폴리오 A"} · ${customer?.aumEokwon ?? 0}억`;

  // 선택 포트폴리오의 절세 효과 — "현재 포트폴리오 대비" 실데이터로 계산.
  // (세전→세후·실효세율 차이, 세액 절감액). 미연결 시 목데이터로 폴백.
  const sel = byId[BACKEND_PORTFOLIO_ID[selectedPortfolioId]]?.base;
  const cur = byId["current"]?.base;
  const liveOk =
    !failed && sel?.afterTaxReturn != null && cur?.afterTaxReturn != null;

  const effect =
    liveOk && sel && cur
      ? {
          annualSavingManwon: Math.round(
            (taxEok(cur, aumEokwon) - taxEok(sel, aumEokwon)) * 10000,
          ),
          subNote:
            selectedPortfolioId === "current"
              ? "현재 포트폴리오 기준 — 제안 A/B 선택 시 절세 효과가 비교됩니다."
              : `현재 포트폴리오 대비 · 세후수익률 ${ppStr(
                  (sel.afterTaxReturn as number) - (cur.afterTaxReturn as number),
                )} · 종합과세·해외양도세 반영`,
          afterTaxReturn: {
            from: pctStr(cur.afterTaxReturn as number),
            to: pctStr(sel.afterTaxReturn as number),
            delta: ppStr(
              (sel.afterTaxReturn as number) - (cur.afterTaxReturn as number),
            ),
          },
          effectiveTax: {
            from: pctStr(effTaxRate(cur)),
            to: pctStr(effTaxRate(sel)),
            delta: ppStr(effTaxRate(sel) - effTaxRate(cur)),
          },
        }
      : TAX_EFFECT;

  // 선택 포트폴리오의 라이브 절세 계산(계좌 배치·제안). 미연결 시 목데이터로 폴백.
  const selStressed = byId[BACKEND_PORTFOLIO_ID[selectedPortfolioId]];
  const liveAccounts = !failed ? selStressed?.accountAllocation : undefined;
  const liveAdvice = !failed ? selStressed?.taxAdvice : undefined;

  // 절세 제안 카드 — 라이브 계산이면 조건 충족(applicable) 카드만, 아니면 목데이터 폴백.
  // 목데이터 폴백 시에도 한도 소진된 계좌 의존 제안은 잔여 한도가 있을 때만 노출한다.
  const mockHeadroom = new Map(
    TAX_EFFECT.accounts
      .filter((a) => a.used !== null && a.limit != null)
      .map((a) => [a.name, (a.limit as number) - (a.used as number)]),
  );
  // 부적합(사유 있음) 카드는 숨기지 않고 회색 + 사유로 표시(PB 설명 근거).
  // 효과 없음/한도 소진(applicable=false & 사유 없음)은 비노출.
  const adviceCards =
    liveAdvice && liveAdvice.length > 0
      ? liveAdvice
          .filter((c) => c.applicable || c.ineligibleReason)
          .map((c) => ({
            icon: ADVICE_META[c.key].icon,
            title: ADVICE_META[c.key].title,
            tag: ADVICE_META[c.key].tag,
            body: ADVICE_META[c.key].body(c),
            savingManwon: c.savingManwon,
            applicable: c.applicable,
            ineligibleReason: c.ineligibleReason ?? null,
          }))
      : TAX_ADVICE.cards
          .filter(
            (c) => !c.accountRef || (mockHeadroom.get(c.accountRef) ?? 0) > 0,
          )
          .map((c) => ({
            icon: c.icon,
            title: c.title,
            tag: c.tag,
            body: c.body,
            savingManwon: c.savingManwon,
            applicable: true,
            ineligibleReason: null as string | null,
          }));
  const adviceTotalManwon = adviceCards.reduce(
    (sum, c) => sum + (c.applicable ? c.savingManwon : 0),
    0,
  );

  // 세금 흐름 비교(라이브) — 동일 세전 기준으로 기존→전환→+절세제안 단계별 세금.
  // 포트폴리오마다 세전수익이 달라 절대 세액 비교는 왜곡되므로 실효세율로 같은 base에 적용.
  const liveFlow =
    liveOk && cur && sel
      ? (() => {
          const pretaxManwon = sel.expectedReturn * aumEokwon * 10000;
          const taxBefore = Math.round(pretaxManwon * effTaxRate(cur));
          const taxSwitch = Math.round(pretaxManwon * effTaxRate(sel));
          const taxFinal = Math.max(taxSwitch - adviceTotalManwon, 0);
          const rows = [
            {
              label: "기존 자산",
              afterTax: Math.round(pretaxManwon - taxBefore),
              tax: taxBefore,
            },
          ];
          // 현재 포트폴리오를 그대로 본 경우엔 '전환' 단계 생략
          if (taxSwitch !== taxBefore) {
            rows.push({
              label: "포트폴리오 전환",
              afterTax: Math.round(pretaxManwon - taxSwitch),
              tax: taxSwitch,
            });
          }
          rows.push({
            label: "+ 절세 제안",
            afterTax: Math.round(pretaxManwon - taxFinal),
            tax: taxFinal,
          });
          return {
            pretaxLabel: `세전 기대수익 ${(pretaxManwon / 10000).toFixed(2)}억 기준`,
            rows,
            totalSavingManwon: taxBefore - taxFinal,
            switchSavingManwon: taxBefore - taxSwitch,
            adviceSavingManwon: taxSwitch - taxFinal,
          };
        })()
      : undefined;

  return (
    <Tabs defaultValue="effect">
      <div className="mb-2 flex items-center justify-between px-0.5">
        <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
        <TabsList className="h-7">
          <TabsTrigger value="effect" className="px-2.5 text-[10px] font-bold">
            절세 효과
          </TabsTrigger>
          <TabsTrigger value="threshold" className="px-2.5 text-[10px] font-bold">
            종합과세 임계선
          </TabsTrigger>
          <TabsTrigger value="advice" className="px-2.5 text-[10px] font-bold">
            절세 제안
          </TabsTrigger>
        </TabsList>
      </div>

      <Card className="gap-0 p-3">
        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex flex-col gap-3">
          <div className="flex items-center gap-4 rounded-xl border border-brand/20 bg-brand/5 px-3.5 py-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 text-xs font-extrabold">
                <span className="flex size-5 items-center justify-center rounded-md bg-brand text-[13px] font-extrabold text-white">
                  $
                </span>
                절세 최적화 효과
                <span className="rounded-full border border-brand/20 bg-white px-2 py-0.5 text-[9.5px] font-bold text-muted-foreground">
                  {baseLabel}
                </span>
              </div>
              <p className="mt-1.5 flex items-baseline gap-1.5 text-[11px] font-bold text-brand-dark">
                연간 절세 효과
                <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                  {effect.annualSavingManwon >= 0 ? "+" : "-"}
                  {splitManwon(effect.annualSavingManwon).value}
                </b>
                <span className="text-[13px] font-extrabold">
                  {splitManwon(effect.annualSavingManwon).unit}
                </span>
              </p>
              <p className="mt-1 text-[9.5px] font-semibold text-muted-foreground">
                {effect.subNote}
              </p>
            </div>
            <SummaryStat
              k="세후 수익률"
              v={`${effect.afterTaxReturn.from} → ${effect.afterTaxReturn.to}`}
              d={effect.afterTaxReturn.delta}
            />
            <SummaryStat
              k="실효세 절감"
              v={`${effect.effectiveTax.from} → ${effect.effectiveTax.to}`}
              d={effect.effectiveTax.delta}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <TaxWaterfall flow={liveFlow} />
            <AccountAllocation accounts={liveAccounts} />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge />
        </TabsContent>

        {/* 탭 3: 절세 제안 */}
        <TabsContent value="advice">
          <div className="grid grid-cols-2 gap-2">
            {adviceCards.map((card) => (
              <div
                key={card.title}
                className={`flex flex-col rounded-xl border p-2.5 ${
                  card.applicable ? "" : "bg-muted/30 opacity-70"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`flex size-5 items-center justify-center rounded-md text-[11px] font-extrabold ${
                      card.applicable
                        ? "bg-brand/10 text-brand-dark"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {card.icon}
                  </span>
                  <span className="text-[11px] font-extrabold">
                    {card.title}
                  </span>
                </div>
                <p className="mt-1.5 flex-1 text-[9px] font-semibold leading-snug text-muted-foreground">
                  {card.body}
                </p>
                <p className="mt-1 text-[8.5px] font-bold text-muted-foreground/60">
                  {card.tag}
                </p>
                {card.applicable ? (
                  <p className="mt-0.5 text-sm font-extrabold tabular-nums text-up">
                    +{formatManwon(card.savingManwon)}
                  </p>
                ) : (
                  <p className="mt-0.5 text-[9px] font-bold leading-snug text-muted-foreground">
                    부적합 · {card.ineligibleReason}
                  </p>
                )}
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between rounded-xl bg-brand px-3 py-2">
            <span className="text-[11px] font-bold text-white">
              {TAX_ADVICE.totalLabel}
            </span>
            <span className="text-base font-extrabold tabular-nums text-white">
              +{formatManwon(adviceTotalManwon)}
            </span>
          </div>
        </TabsContent>
      </Card>
    </Tabs>
  );
}

function SummaryStat({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-2">
      <p className="text-[9.5px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-sm font-extrabold tabular-nums">{v}</p>
      <p className="mt-0.5 text-[10px] font-extrabold tabular-nums text-up">
        {d}
      </p>
    </div>
  );
}
