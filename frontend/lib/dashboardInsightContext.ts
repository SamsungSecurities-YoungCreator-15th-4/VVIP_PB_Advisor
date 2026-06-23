import {
  BACKTEST_SERIES,
  PORTFOLIOS,
  TAX_ADVICE,
  TAX_EFFECT,
  TAX_THRESHOLD,
  type Customer,
} from "@/lib/mockData";
import type { IpsState } from "@/lib/store";

type ScenarioState = { ratePct: number; fxKrw: number };

export interface DashboardInsightContextInput {
  selectedCustomer?: Customer;
  selectedPortfolioId: string;
  ips: IpsState;
  scenario: ScenarioState;
  liveBase: ScenarioState;
  otherIncomeManwon: number;
}

export type DashboardInsightContext = Record<string, unknown>;

function pctToRatio(value: number): number {
  return value / 100;
}

function parseNumber(label: string): number | null {
  const value = Number.parseFloat(label.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(value) ? value : null;
}

function parsePercentToRatio(label: string): number | null {
  const value = parseNumber(label);
  return value == null ? null : value / 100;
}

function parseManwonLabelToWon(label: string): number | null {
  const value = parseNumber(label);
  return value == null ? null : value * 10_000;
}

function toPortfolioSummary(portfolio: (typeof PORTFOLIOS)[number]) {
  const metrics = portfolio.metrics;
  return {
    api_key: portfolio.id,
    name: portfolio.name,
    badge: portfolio.badge,
    weights: portfolio.weights,
    metrics: {
      expected_return: pctToRatio(metrics.expectedReturnPct),
      volatility: pctToRatio(metrics.volatilityPct),
      sharpe_ratio: metrics.sharpe,
      sortino_ratio: metrics.sortino,
      mdd: -pctToRatio(metrics.mddPct),
      after_tax_return: pctToRatio(metrics.afterTaxReturnPct),
      volatility_amount_label: metrics.volatilityAmountLabel,
      mdd_amount_label: metrics.mddAmountLabel,
      after_tax_amount_label: metrics.afterTaxAmountLabel,
    },
  };
}

function portfolioContextKey(id: string): "current" | "portfolio_a" | "portfolio_b" {
  if (id === "current") return "current";
  if (id === "b") return "portfolio_b";
  return "portfolio_a";
}

export function buildDashboardInsightContext({
  selectedCustomer,
  selectedPortfolioId,
  ips,
  scenario,
  liveBase,
  otherIncomeManwon,
}: DashboardInsightContextInput): DashboardInsightContext {
  const selectedPortfolio =
    PORTFOLIOS.find((portfolio) => portfolio.id === selectedPortfolioId) ??
    PORTFOLIOS.find((portfolio) => portfolio.id === "a") ??
    PORTFOLIOS[0];
  const current = PORTFOLIOS.find((portfolio) => portfolio.id === "current");
  const portfolioA = PORTFOLIOS.find((portfolio) => portfolio.id === "a");
  const portfolioB = PORTFOLIOS.find((portfolio) => portfolio.id === "b");

  return {
    schema_version: "dashboard_context_v1",
    selected_customer: selectedCustomer
      ? {
          id: selectedCustomer.id,
          client_id: selectedCustomer.clientId ?? null,
          name: selectedCustomer.name,
          aum_eokwon: selectedCustomer.aumEokwon,
          marginal_rate_pct: selectedCustomer.marginalRatePct,
          age: selectedCustomer.age,
          horizon_years: selectedCustomer.horizonYears,
          near_term_need_manwon: selectedCustomer.nearTermNeedManwon,
          near_term_need_years: selectedCustomer.nearTermNeedYears,
        }
      : null,
    selected_portfolio: {
      id: selectedPortfolio.id,
      name: selectedPortfolio.name,
    },
    ips: {
      goal: ips.goal,
      target_return_pct: ips.returnPct,
      risk_profile: ips.risk,
      time_years: ips.timeYears,
      liquidity: ips.liquidity,
      tax: ips.tax,
      legal: ips.legal,
      unique: ips.unique,
    },
    benchmark_choice: "all",
    current: current ? toPortfolioSummary(current) : null,
    portfolio_a: portfolioA ? toPortfolioSummary(portfolioA) : null,
    portfolio_b: portfolioB ? toPortfolioSummary(portfolioB) : null,
    backtest: {
      period: "최근 5년",
      index_base: 100,
      series: BACKTEST_SERIES,
    },
    stress: {
      live_base: liveBase,
      selected_scenario: scenario,
      deltas: {
        rate_pct: scenario.ratePct - liveBase.ratePct,
        fx_krw: scenario.fxKrw - liveBase.fxKrw,
      },
    },
    tax_optimizer: {
      selected_portfolio_key: portfolioContextKey(selectedPortfolio.id),
      current: {
        headline: {
          annual_tax_saving: TAX_EFFECT.annualSavingManwon * 10_000,
          after_tax_return_before: parsePercentToRatio(
            TAX_EFFECT.afterTaxReturn.from,
          ),
          after_tax_return_after: parsePercentToRatio(
            TAX_EFFECT.afterTaxReturn.to,
          ),
          tax_amount_before: parseManwonLabelToWon(TAX_EFFECT.effectiveTax.from),
          tax_amount_after: parseManwonLabelToWon(TAX_EFFECT.effectiveTax.to),
        },
      },
      effect: TAX_EFFECT,
      threshold: {
        ...TAX_THRESHOLD,
        other_income_manwon: otherIncomeManwon,
      },
      advice_cards: TAX_ADVICE.cards,
      total_label: TAX_ADVICE.totalLabel,
      total_saving: TAX_ADVICE.totalSaving,
    },
  };
}
