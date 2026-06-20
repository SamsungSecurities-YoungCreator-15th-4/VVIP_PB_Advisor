"""절세 최적화 — 계좌 배치 활용도 + 절세 제안 4종의 실제 절감액 계산.

financial_calc.calc_after_tax_return(세후수익률)과 동일한 자산별 income yield·세법
상수를 재사용한다. 절세 제안의 절감액은 모두 출처 있는 세법 수식으로 산출하며,
조건(종합과세 구간 진입 등)을 충족하지 못하면 applicable=False로 표시해 더미 숫자를
내보내지 않는다.

세법 근거
  - 조세특례제한법 §91의18 (개인종합자산관리계좌, ISA)
      · 연 납입한도 2,000만원 / 누적 한도 1억원
      · 운용수익 비과세 한도 200만원(일반형) — 초과분 9.9% 분리과세
      · ISA 내 손익은 금융소득종합과세 합산에서 제외
  - 소득세법 §59의3 (연금계좌 세액공제) — 연금저축+IRP 합산 공제한도 연 900만원
  - 소득세법 §14③ (금융소득종합과세 기준 2,000만원)
  - 소득세법 §129 (이자·배당 원천징수 15.4%, 만기 10년 이상 장기채권 분리과세 33%)
  - 소득세법 §118의2 (해외주식 양도소득세 22%, 양도손익 통산·기본공제 250만원)
"""
from app.market.financial_calc import (
    ASSET_INCOME_YIELD_ASSUMPTIONS,
    DEFAULT_MARGINAL_INCOME_TAX_RATE,
    DEFAULT_WITHHOLDING_TAX_RATE,
    FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD,
    INCOME_TAXABLE_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS,
    OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE,
    OVERSEAS_STOCK_GAIN_DEDUCTION,
)
from app.market.schemas import AssetAllocation

# ── 세법 상수 (출처: 모듈 docstring) ──────────────────────────────────────────
ISA_ANNUAL_LIMIT_WON = 20_000_000  # 조특법 §91의18 연 납입한도
ISA_TOTAL_LIMIT_WON = 100_000_000  # 조특법 §91의18 누적 납입한도
ISA_TAX_FREE_LIMIT_WON = 2_000_000  # 일반형 비과세 한도(서민·농어민형 400만)
ISA_EXCESS_TAX_RATE = 0.099  # 비과세 초과분 분리과세율(소득세 9% + 지방소득세 0.9%)
ISA_MANDATORY_HOLDING_YEARS = 3  # 조특법 §91의18 ISA 의무가입기간(년)
PENSION_TAX_CREDIT_LIMIT_WON = 9_000_000  # 소득세법 §59의3 연금계좌 세액공제 한도(연)
# 세액공제율: 총급여 5,500만(종합소득 4,500만) 이하 16.5%, 초과 13.2%. VVIP는 초과 가정.
PENSION_TAX_CREDIT_RATE = 0.132
PENSION_RECEIVE_AGE = 55  # 소득세법 §59의3 연금 수령 가능 연령
LONG_BOND_SEPARATE_TAX_RATE = 0.33  # 소득세법 §129 장기채권 분리과세율(30%+지방세)

# 채권성·배당성 자산 분류 (income yield 기준)
_BOND_INCOME_ASSETS = {"general_bond", "low_coupon_bond"}  # 분리과세 미적용 채권
_DIVIDEND_INCOME_ASSETS = {"overseas_dividend", "reit"}  # 고배당성 자산


def _income_won_by_asset(
    portfolio: list[AssetAllocation], gross_return: float, total_won: float
) -> dict[str, float]:
    """자산군별 연간 이자·배당성 금융소득(원). financial_calc와 동일 가정:
    income = weight × 총자산 × min(기대수익률, 자산별 income yield)."""
    out: dict[str, float] = {}
    if gross_return <= 0 or total_won <= 0:
        return out
    for a in portfolio:
        if a.assetClass in INCOME_TAXABLE_ASSETS:
            y = ASSET_INCOME_YIELD_ASSUMPTIONS[a.assetClass]
            out[a.assetClass] = out.get(a.assetClass, 0.0) + a.weight * total_won * min(
                gross_return, max(y, 0.0)
            )
    return out


def _overseas_capital_gain_won(
    portfolio: list[AssetAllocation], gross_return: float, total_won: float
) -> float:
    """해외상장 주식·ETF의 연간 가격차익(원) = 총이익 − 이자·배당분.
    전량 실현(양도) 가정 시 양도손익 통산 대상이 되는 금액."""
    if gross_return <= 0 or total_won <= 0:
        return 0.0
    gain = 0.0
    for a in portfolio:
        if a.assetClass in OVERSEAS_STOCK_CAPITAL_GAIN_ASSETS:
            total_profit = a.weight * total_won * gross_return
            income_part = 0.0
            if a.assetClass in INCOME_TAXABLE_ASSETS:
                y = ASSET_INCOME_YIELD_ASSUMPTIONS[a.assetClass]
                income_part = a.weight * total_won * min(gross_return, max(y, 0.0))
            gain += max(total_profit - income_part, 0.0)
    return gain


def _won_to_manwon(won: float) -> int:
    """원 → 만원 반올림(정수)."""
    return int(round(won / 10_000))


def calc_account_allocation(
    isa_used_manwon: float, pension_used_manwon: float
) -> list[dict]:
    """절세 계좌 배치 활용도 — 법정 한도(상수) 대비 고객 기납입액(입력)."""
    return [
        {
            "key": "isa",
            "usedManwon": int(round(isa_used_manwon)),
            "limitManwon": _won_to_manwon(ISA_ANNUAL_LIMIT_WON),
        },
        {
            "key": "pension",
            "usedManwon": int(round(pension_used_manwon)),
            "limitManwon": _won_to_manwon(PENSION_TAX_CREDIT_LIMIT_WON),
        },
        {"key": "general", "usedManwon": None, "limitManwon": None},
    ]


def calc_tax_advice(
    portfolio: list[AssetAllocation],
    gross_return: float,
    total_assets: float,  # 억 원
    isa_used_manwon: float,
    realized_loss_manwon: float,
    other_financial_income: float = 0.0,  # 억 원
    marginal_income_tax_rate: float = DEFAULT_MARGINAL_INCOME_TAX_RATE,
    *,
    pension_used_manwon: float = 0.0,
    age: int | None = None,
    horizon_years: float | None = None,
    near_term_need_manwon: float = 0.0,
    near_term_need_years: float | None = None,
    isa_opened: bool = True,
) -> list[dict]:
    """절세 제안 6종의 절감액(만원)을 실제 세법 수식 + 적합성(lock-up) 게이팅으로 산출.

    반환 각 항목: {key, savingManwon, applicable, transferableManwon, ineligibleReason}.
    - applicable=False & ineligibleReason 있음 → 제도상 부적합(사유 표시, 합산 제외).
    - applicable=False & ineligibleReason 없음 → 절감 효과 없음/한도 소진(비노출 권장).

    적합성 입력
      - age: 고객 나이 (연금 55세 수령요건 게이팅)
      - horizon_years: 투자기간(년) — ISA 3년 의무보유·연금 수령까지 기간과 비교
      - near_term_need_manwon / _years: 단기 필요자금(금액·시점) — 묶이는 금액에서 제외
      - isa_opened: ISA 기존 개설 여부. False면 신규 개설 가능 판정(직전 종합과세 대상 추정 시 불가)
    """
    total_won = max(total_assets, 0.0) * 1e8
    other_income_won = max(other_financial_income, 0.0) * 1e8
    income_by_asset = _income_won_by_asset(portfolio, gross_return, total_won)

    # 포트폴리오 전체 이자·배당성 금융소득 + 고객의 다른 금융소득
    total_financial_income_won = sum(income_by_asset.values()) + other_income_won
    # 종합과세 구간 초과분(2,000만원 초과) — 추가과세(한계세율−원천징수) 대상
    excess_won = max(
        total_financial_income_won - FINANCIAL_INCOME_COMPREHENSIVE_TAX_THRESHOLD, 0.0
    )
    extra_rate = max(marginal_income_tax_rate - DEFAULT_WITHHOLDING_TAX_RATE, 0.0)
    # 직전 금융소득종합과세 대상(추정) — 현재 포트폴리오 금융소득이 유지됐다는 가정.
    # ISA는 직전 3개 과세기간 중 1회라도 종합과세 대상이면 신규 가입 불가(조특법 §91의18).
    is_comprehensive = excess_won > 0
    # lock-up 가능한(= 단기 필요자금을 제외한) 여유 자금
    investable_won = max(total_won - max(near_term_need_manwon, 0.0) * 10_000, 0.0)

    cards: list[dict] = []

    # ── ① ISA 계좌 활용 ─────────────────────────────────────────────────────
    # 잔여 한도(연 2,000만)만큼 이자·배당성 자산을 ISA로 이전 → 비과세 200만 +
    # 초과분 9.9% 분리과세 + 종합과세 합산 제외. 현행(일반계좌) 세부담과 비교한 절감액.
    isa_headroom_won = max(ISA_ANNUAL_LIMIT_WON - isa_used_manwon * 10_000, 0.0)
    income_asset_value_won = sum(
        a.weight * total_won
        for a in portfolio
        if a.assetClass in INCOME_TAXABLE_ASSETS
    )
    # 이전 가능액은 한도·이자배당자산 평가액·단기필요자금 제외 여유자금 중 최소.
    transferable_won = min(isa_headroom_won, income_asset_value_won, investable_won)
    isa_saving_won = 0.0
    isa_applicable = False
    isa_reason: str | None = None
    # 신규 개설 가능 여부 게이팅(기존 미개설 고객에 한함)
    if not isa_opened and is_comprehensive:
        isa_reason = "직전 금융소득종합과세 대상(추정) → ISA 신규 개설 불가"
    elif (
        not isa_opened
        and horizon_years is not None
        and horizon_years < ISA_MANDATORY_HOLDING_YEARS
    ):
        isa_reason = (
            f"투자기간 {horizon_years:g}년 < ISA 의무보유기간 "
            f"{ISA_MANDATORY_HOLDING_YEARS}년"
        )
    if isa_reason is None and transferable_won > 0 and income_asset_value_won > 0:
        # 이전 자산의 실효 income 비율(평가액 대비 금융소득)
        avg_income_rate = sum(income_by_asset.values()) / income_asset_value_won
        moved_income_won = transferable_won * avg_income_rate
        # 현행: 원천징수 15.4% + (종합과세 구간에 걸리는 부분) 추가과세
        comp_portion_won = min(moved_income_won, excess_won)
        tax_outside_won = (
            moved_income_won * DEFAULT_WITHHOLDING_TAX_RATE
            + comp_portion_won * extra_rate
        )
        # ISA 내: 비과세 200만 초과분만 9.9% 분리과세
        tax_isa_won = max(moved_income_won - ISA_TAX_FREE_LIMIT_WON, 0.0) * ISA_EXCESS_TAX_RATE
        isa_saving_won = max(tax_outside_won - tax_isa_won, 0.0)
        isa_applicable = isa_saving_won > 0
    cards.append(
        {
            "key": "isa",
            "savingManwon": _won_to_manwon(isa_saving_won) if isa_applicable else 0,
            "applicable": isa_applicable,
            "transferableManwon": _won_to_manwon(transferable_won) if isa_applicable else 0,
            "ineligibleReason": isa_reason,
        }
    )

    # ── ② 연금계좌 세액공제 ─────────────────────────────────────────────────
    # 연금저축+IRP 잔여 세액공제 한도(연 900만) 납입 → 13.2% 세액공제.
    # 단, 만 55세 이후 + 가입 5년 이상이라야 수령 가능(중도해지 시 기타소득세 16.5%).
    pension_headroom_won = max(
        PENSION_TAX_CREDIT_LIMIT_WON - max(pension_used_manwon, 0.0) * 10_000, 0.0
    )
    pension_saving_won = min(pension_headroom_won, investable_won) * PENSION_TAX_CREDIT_RATE
    pension_reason: str | None = None
    if age is not None and age < PENSION_RECEIVE_AGE:
        years_to_receive = PENSION_RECEIVE_AGE - age
        if horizon_years is not None and horizon_years < years_to_receive:
            pension_reason = (
                f"투자기간 {horizon_years:g}년 < 연금 수령까지 {years_to_receive:g}년"
            )
    pension_applicable = pension_reason is None and pension_saving_won > 0
    cards.append(
        {
            "key": "pension_credit",
            "savingManwon": _won_to_manwon(pension_saving_won) if pension_applicable else 0,
            "applicable": pension_applicable,
            "transferableManwon": (
                _won_to_manwon(min(pension_headroom_won, investable_won))
                if pension_applicable
                else 0
            ),
            "ineligibleReason": pension_reason,
        }
    )

    # ── ② 분리과세 채권 ─────────────────────────────────────────────────────
    # 일반채·저쿠폰채 이자 중 종합과세 구간에 걸리는 부분을 장기채권 분리과세(33%)로
    # 종결 → 한계세율 대신 33% 적용. 종합과세 구간 진입 시에만 절감 발생.
    bond_income_won = sum(
        income_by_asset.get(c, 0.0) for c in _BOND_INCOME_ASSETS
    )
    bond_eligible_won = min(bond_income_won, excess_won)
    bond_rate_gap = max(marginal_income_tax_rate - LONG_BOND_SEPARATE_TAX_RATE, 0.0)
    bond_saving_won = bond_eligible_won * bond_rate_gap
    cards.append(
        {
            "key": "separate_bond",
            "savingManwon": _won_to_manwon(bond_saving_won),
            "applicable": bond_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None,
        }
    )

    # ── ③ 저율과세 배당주 ───────────────────────────────────────────────────
    # 고배당(해외배당·리츠) 중 종합과세 구간에 걸리는 배당소득을 저배당·자본이득형으로
    # 조정 → 종합과세 추가과세분(한계세율−15.4%) 회피(미실현 자본이득 가정).
    dividend_income_won = sum(
        income_by_asset.get(c, 0.0) for c in _DIVIDEND_INCOME_ASSETS
    )
    dividend_eligible_won = min(dividend_income_won, excess_won)
    dividend_saving_won = dividend_eligible_won * extra_rate
    cards.append(
        {
            "key": "low_tax_dividend",
            "savingManwon": _won_to_manwon(dividend_saving_won),
            "applicable": dividend_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None,
        }
    )

    # 해외주식 연간 양도차익(전량 실현 가정) — ⑤·⑥ 공통 입력
    overseas_gain_won = _overseas_capital_gain_won(portfolio, gross_return, total_won)

    # ── ⑤ 해외주식 양도 250만원 기본공제 활용 ───────────────────────────────
    # 매년 양도차익을 기본공제 한도(250만원)까지 실현해 비과세로 확정 → 그만큼 22% 절감.
    exemption_realizable_won = min(overseas_gain_won, OVERSEAS_STOCK_GAIN_DEDUCTION)
    exemption_saving_won = exemption_realizable_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    cards.append(
        {
            "key": "overseas_exemption",
            "savingManwon": _won_to_manwon(exemption_saving_won),
            "applicable": exemption_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None,
        }
    )

    # ── ⑥ Tax-loss Harvesting ───────────────────────────────────────────────
    # 평가손실을 확정해 해외주식 양도차익과 통산 → 통산액 × 22% 절감.
    # (보수적으로 250만원 기본공제는 잔여 양도차익에 적용되는 것으로 보아 미반영)
    realized_loss_won = max(realized_loss_manwon, 0.0) * 10_000
    offset_won = min(realized_loss_won, overseas_gain_won)
    harvest_saving_won = offset_won * OVERSEAS_STOCK_CAPITAL_GAINS_TAX_RATE
    cards.append(
        {
            "key": "tax_loss",
            "savingManwon": _won_to_manwon(harvest_saving_won),
            "applicable": harvest_saving_won > 0,
            "transferableManwon": 0,
            "ineligibleReason": None,
        }
    )

    return cards
