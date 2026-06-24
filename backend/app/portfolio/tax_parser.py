# ruff: noqa: E501
"""Tax/Unique 자유 텍스트를 구조화하는 결정론적 파서.

원칙
- low/medium/high 같은 세금 민감도 추론을 하지 않는다.
- 원문, 매칭 규칙, 근거 문구를 보존한다.
- 발화에 명시된 사실만 기존 세금·계좌 계산 입력으로 연결한다.
- 지원하지 않는 세목은 advisory route로 남기며 임의 세액을 계산하지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


MAX_TEXT_LENGTH = 4000
MONEY_UNITS = {
    "조": 1_000_000_000_000,
    "억": 100_000_000,
    "천만": 10_000_000,
    "백만": 1_000_000,
    "십만": 100_000,
    "만": 10_000,
    "천": 1_000,
}
MONEY_TOKEN_PATTERN = (
    r"[0-9][0-9,]*(?:\.[0-9]+)?\s*"
    r"(?:조|억|천\s*만|백\s*만|십\s*만|만|천)"
)
MONEY_EXPRESSION_PATTERN = (
    rf"((?:{MONEY_TOKEN_PATTERN}\s*)+\s*원?|"
    r"[0-9][0-9,]*(?:\.[0-9]+)?\s*원)"
)


def _rule(
    aliases: Sequence[str],
    *,
    route: str,
    effect: str,
    required_facts: Sequence[str] = (),
    support_level: str = "advisory",
) -> Dict[str, Any]:
    return {
        "aliases": tuple(aliases),
        "route": route,
        "recommendation_effect": effect,
        "required_facts": tuple(required_facts),
        "support_level": support_level,
    }


# 새 세목을 지원할 때 if문을 흩뿌리지 않고 이 레지스트리에 한 항목을 추가한다.
TAX_TOPIC_REGISTRY: Dict[str, Dict[str, Any]] = {
    # 금융투자·계좌·절세: 현재 엔진 계산과 직접 연결 가능한 주제
    "financial_income_comprehensive_tax": _rule(
        ("금융소득종합과세", "금융 소득 종합 과세", "금소종", "금소세"),
        route="financial_income.comprehensive",
        effect="after_tax_return",
        required_facts=("external_financial_income_krw",),
        support_level="calculation",
    ),
    "interest_income_tax": _rule(
        ("이자소득세", "이자 소득세", "이자소득 과세"),
        route="financial_income.interest",
        effect="after_tax_return",
        support_level="calculation",
    ),
    "dividend_income_tax": _rule(
        ("배당소득세", "배당 소득세", "배당소득 과세"),
        route="financial_income.dividend",
        effect="after_tax_return",
        support_level="calculation",
    ),
    "high_dividend_separate_taxation": _rule(
        ("고배당 분리과세", "배당소득 분리과세", "배당 분리과세"),
        route="financial_income.high_dividend_separate",
        effect="after_tax_return",
    ),
    "foreign_dividend_withholding_tax": _rule(
        ("해외배당 원천징수", "외국배당 원천징수", "미국배당 원천징수"),
        route="cross_border.foreign_dividend_withholding",
        effect="after_tax_return",
    ),
    "foreign_tax_credit": _rule(
        ("외국납부세액공제", "외납세액공제", "외국 세액공제"),
        route="cross_border.foreign_tax_credit",
        effect="after_tax_return",
    ),
    "overseas_stock_capital_gains_tax": _rule(
        ("해외주식 양도세", "해외 주식 양도세", "해외주식 양도소득세", "미국주식 양도세", "미장 양도세"),
        route="capital_gains.overseas_stock",
        effect="after_tax_return",
        required_facts=("overseas_realized_gain_krw",),
        support_level="calculation",
    ),
    "capital_gains_tax_unspecified": _rule(
        ("양도세", "양도 소득세", "양도소득세"),
        route="capital_gains.unspecified",
        effect="additional_input_required",
    ),
    "domestic_stock_major_shareholder_capital_gains_tax": _rule(
        ("대주주 양도세", "국내주식 대주주 양도소득세", "상장주식 대주주 양도세"),
        route="capital_gains.domestic_major_shareholder",
        effect="after_tax_return",
    ),
    "unlisted_stock_capital_gains_tax": _rule(
        ("비상장주식 양도세", "비상장 주식 양도소득세"),
        route="capital_gains.unlisted_stock",
        effect="after_tax_return",
    ),
    "securities_transaction_tax": _rule(
        ("증권거래세", "주식 거래세"),
        route="transaction_tax.securities",
        effect="net_return",
    ),
    "derivatives_capital_gains_tax": _rule(
        ("파생상품 양도소득세", "선물옵션 양도세", "파생상품 세금"),
        route="capital_gains.derivatives",
        effect="after_tax_return",
    ),
    "fund_etf_taxation": _rule(
        ("펀드 과세", "ETF 과세", "상장지수펀드 과세", "펀드 세금", "ETF 세금"),
        route="investment_product.fund_etf",
        effect="after_tax_return",
    ),
    "bond_interest_tax": _rule(
        ("채권 이자소득세", "채권이자 과세", "채권 세금"),
        route="investment_product.bond_interest",
        effect="after_tax_return",
    ),
    "separate_taxation_product": _rule(
        ("분리과세 상품", "분리과세 채권", "분리과세채", "분리 과세"),
        route="investment_product.separate_tax",
        effect="after_tax_return",
        support_level="calculation",
    ),
    "tax_loss_harvesting": _rule(
        ("절세매도", "절세 매도", "손실실현", "손실 실현"),
        route="capital_gains.tax_loss_harvesting",
        effect="after_tax_return",
    ),
    "gain_loss_offset": _rule(
        ("손익통산", "손익 통산", "손실상계", "손실 상계"),
        route="capital_gains.gain_loss_offset",
        effect="after_tax_return",
    ),
    "isa": _rule(
        ("ISA", "개인종합자산관리계좌", "개인 종합자산관리계좌"),
        route="account.isa",
        effect="after_tax_return_and_lockup",
        support_level="calculation",
    ),
    "irp": _rule(
        ("IRP", "개인형퇴직연금", "개인형 퇴직연금"),
        route="account.irp",
        effect="after_tax_return_and_lockup",
        support_level="calculation",
    ),
    "pension_savings": _rule(
        ("연금저축", "연금 저축"),
        route="account.pension_savings",
        effect="after_tax_return_and_lockup",
    ),
    "pension_income_tax": _rule(
        ("연금소득세", "연금 수령 세금", "연금 과세"),
        route="pension.income_tax",
        effect="after_tax_return_and_lockup",
    ),

    # 자산이전·승계: 세율을 추정하지 않고 필요금액·시점·검토 제약으로 연결
    "gift_tax": _rule(
        ("증여세", "사전증여", "사전 증여", "증여"),
        route="wealth_transfer.gift",
        effect="liquidity_constraint",
        required_facts=("transfer_amount_krw", "transfer_horizon_years"),
        support_level="constraint_or_advisory",
    ),
    "inheritance_tax": _rule(
        ("상속세", "상속"),
        route="wealth_transfer.inheritance",
        effect="liquidity_constraint",
        required_facts=("transfer_amount_krw", "transfer_horizon_years"),
        support_level="constraint_or_advisory",
    ),
    "business_succession": _rule(
        ("가업승계", "기업승계", "경영권 승계"),
        route="wealth_transfer.business_succession",
        effect="liquidity_and_legal_constraint",
    ),
    "business_inheritance_deduction": _rule(
        ("가업상속공제", "가업 상속 공제"),
        route="wealth_transfer.business_inheritance_deduction",
        effect="legal_review",
    ),
    "business_succession_gift_tax_special_case": _rule(
        ("가업승계 증여세 특례", "가업주식 증여세 특례"),
        route="wealth_transfer.business_gift_special",
        effect="legal_review",
    ),
    "burdened_gift": _rule(
        ("부담부증여", "부담부 증여"),
        route="wealth_transfer.burdened_gift",
        effect="liquidity_and_legal_constraint",
    ),
    "pre_inheritance_gift": _rule(
        ("상속 전 증여", "사전 증여 계획"),
        route="wealth_transfer.pre_inheritance_gift",
        effect="liquidity_and_legal_constraint",
    ),
    "family_business_share_transfer": _rule(
        ("가족법인 지분이전", "가족 법인 지분 이전", "가업주식 이전"),
        route="wealth_transfer.family_business_share",
        effect="legal_review",
    ),
    "corporate_personal_asset_separation": _rule(
        ("법인자산 개인자산 분리", "법인 자금과 개인 자금", "법인·개인 자산"),
        route="corporate.asset_separation",
        effect="scope_constraint",
    ),

    # 부동산
    "real_estate_tax_unspecified": _rule(
        ("부동산 세금", "부동산세", "부동산"),
        route="real_estate.unspecified",
        effect="additional_input_required",
    ),
    "real_estate_capital_gains_tax": _rule(
        ("부동산 양도세", "아파트 양도세", "주택 양도소득세", "토지 양도세"),
        route="real_estate.capital_gains",
        effect="liquidity_and_advisory",
    ),
    "acquisition_tax": _rule(
        ("취득세",),
        route="real_estate.acquisition",
        effect="liquidity_constraint",
    ),
    "property_tax": _rule(
        ("재산세",),
        route="real_estate.property",
        effect="liquidity_constraint",
    ),
    "comprehensive_real_estate_holding_tax": _rule(
        ("종합부동산세", "종부세"),
        route="real_estate.comprehensive_holding",
        effect="liquidity_constraint",
    ),
    "rental_income_tax": _rule(
        ("임대소득세", "주택임대소득", "임대 소득세"),
        route="real_estate.rental_income",
        effect="external_income_context",
    ),
    "commercial_property_vat": _rule(
        ("상가 부가가치세", "상업용 부동산 부가세"),
        route="real_estate.commercial_vat",
        effect="advisory",
    ),
    "reconstruction_redevelopment_tax": _rule(
        ("재건축 세금", "재개발 세금", "재건축 부담금"),
        route="real_estate.reconstruction",
        effect="advisory",
    ),
    "housing_right_capital_gains_tax": _rule(
        ("입주권 양도세", "분양권 양도세"),
        route="real_estate.housing_right_capital_gains",
        effect="advisory",
    ),
    "burdened_gift_real_estate": _rule(
        ("부동산 부담부증여", "주택 부담부 증여"),
        route="real_estate.burdened_gift",
        effect="liquidity_and_legal_constraint",
    ),

    # 법인·사업자
    "corporate_income_tax": _rule(
        ("법인세",),
        route="corporate.income_tax",
        effect="scope_constraint",
    ),
    "comprehensive_income_tax": _rule(
        ("종합소득세",),
        route="individual.comprehensive_income_tax",
        effect="external_income_context",
    ),
    "business_income_tax": _rule(
        ("사업소득세", "사업 소득세"),
        route="business.income_tax",
        effect="external_income_context",
    ),
    "value_added_tax": _rule(
        ("부가가치세", "부가세"),
        route="business.vat",
        effect="advisory",
    ),
    "shareholder_dividend_tax": _rule(
        ("주주 배당 과세", "법인 배당소득세", "오너 배당 세금"),
        route="corporate.shareholder_dividend",
        effect="external_income_context",
    ),
    "executive_compensation_tax": _rule(
        ("임원 보수 세금", "대표자 급여 과세", "임원 상여 과세"),
        route="corporate.executive_compensation",
        effect="external_income_context",
    ),
    "deemed_dividend": _rule(
        ("의제배당", "의제 배당"),
        route="corporate.deemed_dividend",
        effect="advisory",
    ),
    "related_party_transaction_tax": _rule(
        ("특수관계인 거래", "부당행위계산부인", "특수관계자 과세"),
        route="corporate.related_party",
        effect="legal_review",
    ),
    "corporate_share_transfer_tax": _rule(
        ("법인주식 양도세", "법인 지분 양도세"),
        route="corporate.share_transfer",
        effect="advisory",
    ),

    # 국제·해외
    "overseas_financial_account_reporting": _rule(
        ("해외금융계좌 신고", "해외 금융계좌 신고"),
        route="cross_border.account_reporting",
        effect="compliance_review",
    ),
    "nonresident_withholding_tax": _rule(
        ("비거주자 원천징수", "비거주자 과세"),
        route="cross_border.nonresident_withholding",
        effect="after_tax_return_or_advisory",
    ),
    "exit_tax": _rule(
        ("국외전출세", "출국세"),
        route="cross_border.exit_tax",
        effect="legal_review",
    ),
    "overseas_trust_reporting": _rule(
        ("해외신탁 신고", "해외 신탁 과세"),
        route="cross_border.overseas_trust",
        effect="compliance_review",
    ),
    "foreign_virtual_asset_account_reporting": _rule(
        ("해외 가상자산계좌 신고", "해외 코인계좌 신고"),
        route="cross_border.virtual_asset_reporting",
        effect="compliance_review",
    ),
    "tax_residency_status": _rule(
        ("세법상 거주자", "세무상 거주자", "조세 거주지", "비거주자"),
        route="cross_border.tax_residency",
        effect="scope_constraint",
    ),

    # 기타·비주류
    "virtual_asset_taxation": _rule(
        ("가상자산 과세", "코인 세금", "암호화폐 세금"),
        route="other.virtual_asset",
        effect="advisory",
    ),
    "insurance_proceeds_inheritance_tax": _rule(
        ("보험금 상속세", "사망보험금 상속세"),
        route="other.insurance_inheritance",
        effect="advisory",
    ),
    "trust_taxation": _rule(
        ("신탁 과세", "신탁 세금"),
        route="other.trust",
        effect="advisory",
    ),
    "stock_option_tax": _rule(
        ("스톡옵션 세금", "주식매수선택권 과세"),
        route="other.stock_option",
        effect="external_income_context",
    ),
    "employee_invention_compensation_tax": _rule(
        ("직무발명보상금 과세", "직무발명 보상금 세금"),
        route="other.employee_invention",
        effect="external_income_context",
    ),
    "private_equity_fund_taxation": _rule(
        ("사모펀드 과세", "PEF 과세"),
        route="other.private_equity",
        effect="advisory",
    ),
    "partnership_taxation": _rule(
        ("동업기업 과세", "파트너십 과세"),
        route="other.partnership",
        effect="advisory",
    ),
    "membership_right_capital_gains_tax": _rule(
        ("회원권 양도세", "골프회원권 양도세"),
        route="other.membership_right",
        effect="advisory",
    ),
    "artwork_collectible_taxation": _rule(
        ("미술품 과세", "골동품 과세", "수집품 세금"),
        route="other.art_collectible",
        effect="advisory",
    ),
    "ship_aircraft_capital_gains_tax": _rule(
        ("선박 양도세", "항공기 양도세"),
        route="other.ship_aircraft",
        effect="advisory",
    ),
    "non_business_land_tax": _rule(
        ("비사업용 토지", "비사업용토지 양도세"),
        route="other.non_business_land",
        effect="advisory",
    ),
    "nominee_ownership_deemed_gift": _rule(
        ("명의신탁 증여의제", "명의 신탁 증여"),
        route="other.nominee_deemed_gift",
        effect="legal_review",
    ),
    "low_price_transfer_deemed_gift": _rule(
        ("저가양수 증여의제", "고가양도 증여의제", "저가 양도 증여"),
        route="other.low_price_transfer",
        effect="legal_review",
    ),
    "interest_free_loan_deemed_gift": _rule(
        ("무이자 대여 증여", "금전 무상대출 증여"),
        route="other.interest_free_loan",
        effect="legal_review",
    ),
    "controlled_foreign_corporation_tax": _rule(
        ("특정외국법인 유보소득", "CFC 과세", "조세피난처 과세"),
        route="cross_border.cfc",
        effect="advisory",
    ),
    "tax_penalty_and_late_payment": _rule(
        ("가산세", "납부지연가산세", "신고불성실가산세"),
        route="other.penalty",
        effect="liquidity_constraint",
    ),
    "general_tax_concern": _rule(
        ("세금", "절세", "세부담", "세 부담"),
        route="tax.general_review",
        effect="additional_input_required",
    ),
}


COST_TOPIC_REGISTRY: Dict[str, Dict[str, Any]] = {
    "brokerage_fee": _rule(
        ("매매수수료", "거래 수수료", "증권사 수수료", "브로커리지 수수료"),
        route="cost.brokerage",
        effect="net_return",
    ),
    "transaction_cost": _rule(
        ("거래비용", "거래 비용"),
        route="cost.transaction",
        effect="net_return",
    ),
    "exchange_fee": _rule(
        ("환전수수료", "환전 수수료"),
        route="cost.exchange_fee",
        effect="net_return",
    ),
    "fx_spread": _rule(
        ("환율 스프레드", "환전 스프레드"),
        route="cost.fx_spread",
        effect="net_return",
    ),
    "fund_management_fee": _rule(
        ("펀드 보수", "운용보수", "운용 보수"),
        route="cost.fund_management",
        effect="net_return",
    ),
    "etf_expense_ratio": _rule(
        ("ETF 총보수", "ETF 보수", "총보수비용"),
        route="cost.etf_expense",
        effect="net_return",
    ),
    "performance_fee": _rule(
        ("성과보수", "성과 보수"),
        route="cost.performance_fee",
        effect="net_return",
    ),
    "early_redemption_fee": _rule(
        ("중도해지수수료", "중도 해지 수수료", "환매수수료"),
        route="cost.early_redemption",
        effect="net_return_or_liquidity",
    ),
    "remittance_fee": _rule(
        ("송금수수료", "해외송금 수수료"),
        route="cost.remittance",
        effect="net_return",
    ),
    "custody_fee": _rule(
        ("보관수수료", "수탁수수료", "커스터디 수수료"),
        route="cost.custody",
        effect="net_return",
    ),
    "fee_unspecified": _rule(
        ("수수료",),
        route="cost.unspecified_fee",
        effect="additional_input_required",
    ),
}


STATUS_PATTERNS: Sequence[Tuple[str, str]] = (
    ("ineligible", r"가입\s*불가|이용\s*불가|적격\s*아님|대상\s*아님"),
    ("not_applicable", r"이력\s*없|해당\s*없|없음|없다|미가입|가입하지\s*않|안\s*만들"),
    ("history", r"과거|이력|최근\s*[0-9]+\s*년|예전에"),
    ("planned", r"예정|계획|향후|앞으로|하려고|하고\s*싶"),
    ("concern", r"걱정|우려|부담|관심|줄이고\s*싶|절세"),
)


def stringify_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " | ".join(f"{key}: {stringify_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " | ".join(stringify_text(item) for item in value)
    return str(value)


def parse_money_krw(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "").strip()
    if not text:
        return None

    total = 0.0
    matched = False
    unit_pattern = r"조|억|천\s*만|백\s*만|십\s*만|만|천"
    for number_text, unit in re.findall(
        rf"([0-9]+(?:\.[0-9]+)?)\s*({unit_pattern})", text
    ):
        normalized_unit = re.sub(r"\s+", "", unit)
        total += float(number_text) * MONEY_UNITS[normalized_unit]
        matched = True
    if matched:
        return total

    won = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*원", text)
    if won:
        return float(won.group(1))

    plain = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*", text)
    return float(plain.group(1)) if plain else None


def _context(text: str, start: int, end: int, radius: int = 45) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()


def _status_from_context(context: str) -> str:
    for status, pattern in STATUS_PATTERNS:
        if re.search(pattern, context, flags=re.IGNORECASE):
            return status
    return "current"


def _iter_alias_matches(text: str, aliases: Iterable[str]) -> Iterable[Tuple[re.Match[str], str]]:
    # 더 구체적인 표현을 먼저 매칭해 "해외주식 양도세"가 일반 "양도세"로만 잡히는 것을 방지한다.
    for alias in sorted(set(aliases), key=len, reverse=True):
        pattern = re.escape(alias).replace(r"\ ", r"\s*")
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            yield match, alias


def _match_registry(
    text: str,
    registry: Dict[str, Dict[str, Any]],
    *,
    kind: str,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    occupied: List[Tuple[int, int, str]] = []

    # 구체적 alias가 긴 주제부터 처리한다.
    ordered = sorted(
        registry.items(),
        key=lambda item: max((len(alias) for alias in item[1]["aliases"]), default=0),
        reverse=True,
    )
    for topic, rule in ordered:
        for match, alias in _iter_alias_matches(text, rule["aliases"]):
            start, end = match.span()
            # 동일 구간이 더 구체적인 주제로 이미 잡혔으면 일반 주제의 중복 매칭을 생략한다.
            if any(start >= left and end <= right for left, right, _ in occupied):
                continue
            evidence = _context(text, start, end)
            candidates.append(
                {
                    "kind": kind,
                    "topic": topic,
                    "status": _status_from_context(evidence),
                    "evidence": evidence,
                    "matched_alias": alias,
                    "match_rule": f"{kind}.{topic}.alias",
                    "route": rule["route"],
                    "recommendation_effect": rule["recommendation_effect"],
                    "support_level": rule["support_level"],
                    "required_facts": list(rule["required_facts"]),
                }
            )
            occupied.append((start, end, topic))
            break
    return candidates


def _extract_amount_after_label(text: str, labels: Sequence[str], tail: str = "") -> Optional[float]:
    label_pattern = "|".join(re.escape(label).replace(r"\ ", r"\s*") for label in labels)
    money_pattern = MONEY_EXPRESSION_PATTERN
    pattern = rf"(?:{label_pattern}).{{0,35}}?{money_pattern}{tail}"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return parse_money_krw(match.group(1))


def _extract_year_near(text: str, labels: Sequence[str]) -> Optional[int]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = (
        rf"(?:{label_pattern}).{{0,30}}?(19[0-9]{{2}}|20[0-9]{{2}})\s*년",
        rf"(19[0-9]{{2}}|20[0-9]{{2}})\s*년.{{0,20}}?(?:{label_pattern})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _account_facts(text: str, key: str, aliases: Sequence[str], now_year: int) -> Dict[str, Any]:
    label_pattern = "|".join(re.escape(alias) for alias in aliases)
    start_match = re.search(rf"(?:{label_pattern})", text, flags=re.IGNORECASE)
    if not start_match:
        return {}

    end = min(start_match.start() + 180, len(text))
    other_account_pattern = r"\bIRP\b|개인형\s*퇴직연금" if key == "isa" else r"\bISA\b|개인종합자산관리계좌"
    other_match = re.search(
        other_account_pattern,
        text[start_match.end():end],
        flags=re.IGNORECASE,
    )
    if other_match:
        end = start_match.end() + other_match.start()
    segment = text[start_match.start():end]

    facts: Dict[str, Any] = {}
    status = _status_from_context(segment)
    if status == "ineligible":
        facts[f"{key}_eligible"] = False
        facts[f"{key}_account_exists"] = False
    elif status == "not_applicable":
        facts[f"{key}_account_exists"] = False
    else:
        facts[f"{key}_account_exists"] = True

    opened_year = _extract_year_near(segment, aliases)
    if opened_year is not None:
        facts[f"{key}_opened_year"] = opened_year
        facts[f"{key}_account_age_years"] = float(max(now_year - opened_year, 0))

    current_contribution = _extract_amount_after_label(
        segment,
        ("올해", "금년", "당해"),
        tail=r".{0,12}(?:납입|입금)",
    )
    if current_contribution is None:
        reverse = re.search(
            rf"{MONEY_EXPRESSION_PATTERN}"
            r".{0,12}(?:올해|금년|당해).{0,12}(?:납입|입금)",
            segment,
            flags=re.IGNORECASE,
        )
        if reverse:
            current_contribution = parse_money_krw(reverse.group(1))
    if current_contribution is not None:
        facts[f"{key}_current_year_contribution_krw"] = current_contribution

    cumulative = _extract_amount_after_label(
        segment,
        ("누적", "현재까지", "총납입", "총 납입"),
        tail=r".{0,12}(?:납입|입금|기여)?",
    )
    if cumulative is not None:
        facts[f"{key}_cumulative_contribution_krw"] = cumulative

    return facts


def _extract_facts(text: str, mentions: List[Dict[str, Any]]) -> Dict[str, Any]:
    now_year = datetime.now(ZoneInfo("Asia/Seoul")).year
    facts: Dict[str, Any] = {}

    facts.update(_account_facts(text, "isa", ("ISA", "개인종합자산관리계좌"), now_year))
    facts.update(_account_facts(text, "irp", ("IRP", "개인형퇴직연금"), now_year))

    external_income_match = re.search(
        r"(?:외부\s*금융소득|기존\s*금융소득|연간\s*금융소득|"
        r"금융소득|이자\s*[·및과와]?\s*배당소득)"
        r"\s*(?:은|는|이|가|약|총|합계|연간)?\s*[:=]?\s*"
        rf"{MONEY_EXPRESSION_PATTERN}",
        text,
        flags=re.IGNORECASE,
    )
    if external_income_match:
        external_income = parse_money_krw(external_income_match.group(1))
        if external_income is not None:
            facts["external_financial_income_krw"] = external_income

    marginal_rate_match = re.search(
        r"(?:한계세율|종합소득세율|적용세율).{0,20}?([0-9]+(?:\.[0-9]+)?)\s*%",
        text,
        flags=re.IGNORECASE,
    )
    if marginal_rate_match:
        facts["marginal_income_tax_rate"] = float(marginal_rate_match.group(1)) / 100.0

    realized_loss = _extract_amount_after_label(
        text,
        ("해외주식 실현손실", "해외주식 손실", "실현손실", "손실실현"),
    )
    if realized_loss is not None:
        facts["overseas_realized_loss_krw"] = realized_loss

    realized_gain = _extract_amount_after_label(
        text,
        ("해외주식 실현이익", "해외주식 이익", "실현이익", "양도차익"),
    )
    if realized_gain is not None:
        facts["overseas_realized_gain_krw"] = realized_gain

    history_segment = re.search(
        r"(?:최근\s*3\s*년|최근\s*3개년|3년).{0,40}?"
        r"금융소득종합과세.{0,30}?(?:이력|대상)?"
        r"(?:은|는|이|가)?\s*"
        r"(?P<status>"
        r"있(?:음|다|습니다)?|"
        r"존재(?:함|한다|합니다)?|"
        r"유(?:함|하다|합니다)?|"
        r"대상(?:임|이다|입니다)?|"
        r"해당(?:함|한다|합니다)?|"
        r"없(?:음|다|습니다)?|"
        r"미해당|비대상|무"
        r")",
        text,
        flags=re.IGNORECASE,
    )
    if history_segment:
        history_status = history_segment.group("status")
        facts["isa_recent_3yr_comprehensive_taxed"] = not bool(
            re.match(r"^(?:없|미해당|비대상|무)", history_status)
        )


    transfer_topics = {"gift_tax", "inheritance_tax", "business_succession", "pre_inheritance_gift"}
    if any(item["topic"] in transfer_topics for item in mentions):
        transfer_amount = _extract_amount_after_label(
            text,
            ("증여", "상속", "승계", "이전", "물려"),
        )
        if transfer_amount is None:
            reverse_transfer = re.search(
                rf"{MONEY_EXPRESSION_PATTERN}"
                r".{0,35}?(?:증여|상속|승계|이전|물려)",
                text,
            )
            if reverse_transfer:
                transfer_amount = parse_money_krw(reverse_transfer.group(1))
        if transfer_amount is not None:
            facts["transfer_amount_krw"] = transfer_amount

        horizon_match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*년\s*(?:후|뒤|내|안|이내).{0,40}?(?:증여|상속|승계|이전)",
            text,
        )
        if horizon_match is None:
            horizon_match = re.search(
                r"(?:증여|상속|승계|이전).{0,40}?([0-9]+(?:\.[0-9]+)?)\s*년\s*(?:후|뒤|내|안|이내)",
                text,
            )
        if horizon_match:
            facts["transfer_horizon_years"] = float(horizon_match.group(1))

    return facts


def _build_routes(
    mentions: Sequence[Dict[str, Any]],
    facts: Dict[str, Any],
) -> List[Dict[str, Any]]:
    routes: List[Dict[str, Any]] = []
    for mention in mentions:
        required = mention.get("required_facts", [])
        missing = [key for key in required if facts.get(key) is None]
        routes.append(
            {
                "topic": mention["topic"],
                "module": mention["route"],
                "status": mention["status"],
                "support_level": mention["support_level"],
                "recommendation_effect": mention["recommendation_effect"],
                "can_calculate": (
                    mention["support_level"] == "calculation"
                    and not missing
                    and mention["status"] not in {"not_applicable", "ineligible"}
                ),
                "missing_inputs": missing,
            }
        )
    return routes


def parse_tax_text(value: Any) -> Dict[str, Any]:
    raw_text = stringify_text(value)
    text = raw_text.strip()[:MAX_TEXT_LENGTH]

    tax_mentions = _match_registry(text, TAX_TOPIC_REGISTRY, kind="tax") if text else []
    cost_mentions = _match_registry(text, COST_TOPIC_REGISTRY, kind="cost") if text else []
    all_mentions = [*tax_mentions, *cost_mentions]
    facts = _extract_facts(text, tax_mentions) if text else {}

    return {
        "raw": value,
        "raw_text": raw_text,
        "normalized_text": text,
        "tax_mentions": tax_mentions,
        "cost_mentions": cost_mentions,
        "facts": facts,
        "routes": _build_routes(all_mentions, facts),
        "unmatched_text": [text] if text and not all_mentions else [],
        "parser_version": "deterministic-tax-registry-v1",
        "parser_note": (
            "세금 민감도를 추정하지 않습니다. 원문에서 명시적으로 확인되는 세목·계좌·금액·"
            "기간만 구조화하고, 계산식이 없는 주제는 advisory/constraint route로 보존합니다."
        ),
    }


def apply_tax_profile_to_ips_payload(
    ips_payload: Dict[str, Any],
    tax_value: Any,
) -> Dict[str, Any]:
    """Tax 파서 결과에서 확인된 사실만 기존 계산 입력으로 연결한다."""

    result = dict(ips_payload)
    profile = parse_tax_text(tax_value)
    from .tax_llm_fallback import enrich_tax_profile_with_llm

    profile = enrich_tax_profile_with_llm(profile)
    facts = profile["facts"]
    result["tax_text"] = profile["raw_text"]
    result["tax_profile"] = profile
    result["tax_sensitivity"] = result.get("tax_sensitivity") or None

    def set_if_missing(key: str, value: Any) -> None:
        if value is None:
            return
        current = result.get(key)
        if current is None or current == "":
            result[key] = value

    set_if_missing("external_financial_income_krw", facts.get("external_financial_income_krw"))
    set_if_missing("marginal_income_tax_rate", facts.get("marginal_income_tax_rate"))
    set_if_missing("overseas_realized_loss", facts.get("overseas_realized_loss_krw"))
    set_if_missing("overseas_realized_gain_krw", facts.get("overseas_realized_gain_krw"))

    if "isa_account_exists" in facts:
        result["isa_account_exists"] = bool(facts["isa_account_exists"])
    if facts.get("isa_eligible") is False:
        result["isa_enabled"] = False
        result["isa_existing_account_usable"] = False
    set_if_missing("isa_account_age_years", facts.get("isa_account_age_years"))
    set_if_missing("isa_cumulative_contribution", facts.get("isa_cumulative_contribution_krw"))
    set_if_missing("isa_current_year_contribution", facts.get("isa_current_year_contribution_krw"))
    if "isa_recent_3yr_comprehensive_taxed" in facts:
        result["isa_recent_3yr_comprehensive_taxed"] = bool(
            facts["isa_recent_3yr_comprehensive_taxed"]
        )

    if "irp_account_exists" in facts:
        result["irp_account_exists"] = bool(facts["irp_account_exists"])
    if facts.get("irp_eligible") is False:
        result["irp_enabled"] = False
        result["irp_eligible"] = False
    set_if_missing("irp_account_age_years", facts.get("irp_account_age_years"))
    set_if_missing("irp_cumulative_contribution", facts.get("irp_cumulative_contribution_krw"))
    set_if_missing("irp_current_year_contribution", facts.get("irp_current_year_contribution_krw"))

    transfer_amount = facts.get("transfer_amount_krw")
    transfer_horizon = facts.get("transfer_horizon_years")
    if transfer_amount is not None:
        set_if_missing("unique_need_amount", transfer_amount)
        unique_items = list(result.get("unique_items") or [])
        unique_items.append(
            {
                "type": "wealth_transfer_liquidity_need",
                "amount": transfer_amount,
                "years_until_need": transfer_horizon,
                "source": "tax_text",
            }
        )
        result["unique_items"] = unique_items

        unique_profile = dict(result.get("unique_profile") or {})
        unique_profile["liquidity_need_amount"] = max(
            float(unique_profile.get("liquidity_need_amount") or 0.0),
            float(transfer_amount),
        )
        if transfer_horizon is not None:
            current_horizon = unique_profile.get("liquidity_need_years")
            if current_horizon is None:
                unique_profile["liquidity_need_years"] = transfer_horizon
            else:
                unique_profile["liquidity_need_years"] = min(
                    float(current_horizon),
                    float(transfer_horizon),
                )
        result["unique_profile"] = unique_profile

    return result
