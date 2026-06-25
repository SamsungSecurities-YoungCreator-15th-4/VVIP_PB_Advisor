#!/usr/bin/env python3
"""
PR #172 리뷰 후속 수정 일괄 적용.

- formatters.py의 임시 "# 커밋용" 주석 제거
- Range 응답을 percent 값과 표시 메타데이터로만 제한
- 내부 rate 원본과 원화 금액을 프론트 Range 응답에서 제외
- API 계약의 direction을 higher_is_better로 명시
- 관련 오프라인 테스트 추가

실행:
    저장소 최상위 폴더에서
    python apply_pr172_review_followup.py

Git 명령이나 배포 명령은 실행하지 않습니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

FORMATTERS_PATH = Path("backend/app/portfolio/formatters.py")
CONTRACTS_PATH = Path("backend/app/portfolio/api_contracts.py")
TEST_PATH = Path("backend/tests/test_portfolio_followup.py")

OLD_HELPER = 'def build_metric_range_payload(\n    range_payload: Any,\n) -> Optional[Dict[str, Any]]:\n    """내부 rate 단위의 Monte Carlo Range를 API 표시용 percent 단위로 변환한다."""\n    if not isinstance(range_payload, dict) or not range_payload:\n        return None\n\n    payload = dict(range_payload)\n    rate_value_keys = (\n        "p10",\n        "p20",\n        "p50",\n        "p80",\n        "p90",\n        "lower",\n        "center",\n        "upper",\n    )\n\n    for key in rate_value_keys:\n        if payload.get(key) is not None:\n            payload[key] = rate_to_percent(payload[key])\n\n    payload["unit"] = "percent"\n    return payload\n\n\n'
NEW_HELPER = 'def build_metric_range_payload(\n    range_payload: Any,\n) -> Optional[Dict[str, Any]]:\n    """내부 rate Range를 프론트 표시용 percent 응답으로 제한해 변환한다."""\n    if not isinstance(range_payload, dict) or not range_payload:\n        return None\n\n    rate_value_keys = (\n        "p10",\n        "p20",\n        "p50",\n        "p80",\n        "p90",\n        "lower",\n        "center",\n        "upper",\n    )\n    metadata_keys = (\n        "lower_percentile",\n        "center_percentile",\n        "upper_percentile",\n        "direction",\n    )\n\n    if not any(\n        range_payload.get(key) is not None\n        for key in rate_value_keys\n    ):\n        return None\n\n    # 프론트에는 분위수 % 값과 표시 메타데이터만 전달한다.\n    # 내부 rate 원본, 원화 금액 및 예상치 못한 추가 키는 노출하지 않는다.\n    payload = {\n        key: range_payload[key]\n        for key in (*rate_value_keys, *metadata_keys)\n        if range_payload.get(key) is not None\n    }\n\n    for key in rate_value_keys:\n        if key in payload:\n            payload[key] = rate_to_percent(payload[key])\n\n    payload["unit"] = "percent"\n    return payload\n\n\n'
TESTS_BLOCK = '\n\n\ndef test_metric_range_api_exposes_percent_only() -> None:\n    after_tax_range = {\n        "p10": 0.01,\n        "p20": 0.02,\n        "p50": 0.05,\n        "p80": 0.08,\n        "p90": 0.09,\n        "lower": 0.02,\n        "center": 0.05,\n        "upper": 0.08,\n        "lower_percentile": 20,\n        "center_percentile": 50,\n        "upper_percentile": 80,\n        "unit": "rate",\n        "direction": "higher_is_better",\n        "unexpected_rate": 0.99,\n        "amount": 999_999_999,\n    }\n    mdd_range = {\n        "p10": -0.40,\n        "p20": -0.30,\n        "p50": -0.20,\n        "p80": -0.10,\n        "p90": -0.05,\n        "lower": -0.30,\n        "center": -0.20,\n        "upper": -0.10,\n        "lower_percentile": 20,\n        "center_percentile": 50,\n        "upper_percentile": 80,\n        "unit": "rate",\n        "direction": "higher_is_better",\n        "amount": -600_000_000,\n    }\n\n    payload = build_metrics_payload(\n        {\n            "metrics": {\n                "expected_return": 0.08,\n                "volatility": 0.12,\n                "sharpe_ratio": 0.7,\n                "sortino_ratio": 0.9,\n                "mdd": -0.20,\n                "beta": None,\n                "beta_benchmark": None,\n                "selected_benchmark_key": None,\n                "benchmark_comparisons": {},\n                "after_tax_return": 0.06,\n                "after_tax_return_range": after_tax_range,\n                "mdd_range": mdd_range,\n                "monte_carlo_range_basis": {\n                    "after_tax_return": after_tax_range,\n                    "mdd": mdd_range,\n                },\n            }\n        }\n    )\n\n    assert payload["after_tax_return_range"] == {\n        "p10": 1.0,\n        "p20": 2.0,\n        "p50": 5.0,\n        "p80": 8.0,\n        "p90": 9.0,\n        "lower": 2.0,\n        "center": 5.0,\n        "upper": 8.0,\n        "lower_percentile": 20,\n        "center_percentile": 50,\n        "upper_percentile": 80,\n        "direction": "higher_is_better",\n        "unit": "percent",\n    }\n    assert payload["mdd_range"] == {\n        "p10": -40.0,\n        "p20": -30.0,\n        "p50": -20.0,\n        "p80": -10.0,\n        "p90": -5.0,\n        "lower": -30.0,\n        "center": -20.0,\n        "upper": -10.0,\n        "lower_percentile": 20,\n        "center_percentile": 50,\n        "upper_percentile": 80,\n        "direction": "higher_is_better",\n        "unit": "percent",\n    }\n\n    assert "monte_carlo_range_basis" not in payload\n    assert "unexpected_rate" not in payload["after_tax_return_range"]\n    assert "amount" not in payload["after_tax_return_range"]\n    assert "amount" not in payload["mdd_range"]\n\n\ndef test_empty_metric_range_is_not_exposed() -> None:\n    payload = build_metrics_payload(\n        {\n            "metrics": {\n                "expected_return": 0.08,\n                "volatility": 0.12,\n                "sharpe_ratio": 0.7,\n                "sortino_ratio": 0.9,\n                "mdd": -0.20,\n                "beta": None,\n                "beta_benchmark": None,\n                "selected_benchmark_key": None,\n                "benchmark_comparisons": {},\n                "after_tax_return": 0.06,\n                "after_tax_return_range": {},\n                "mdd_range": {},\n            }\n        }\n    )\n\n    assert payload["after_tax_return_range"] is None\n    assert payload["mdd_range"] is None\n'


def find_repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        required = (
            candidate / FORMATTERS_PATH,
            candidate / CONTRACTS_PATH,
            candidate / TEST_PATH,
        )
        if all(path.is_file() for path in required):
            return candidate
    raise FileNotFoundError(
        "저장소 루트를 찾지 못했습니다.\n"
        "VSCode 터미널을 저장소 최상위 폴더에서 열고 다시 실행해 주세요."
    )


def replace_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label} 위치를 정확히 찾지 못했습니다. "
            f"예상 횟수=1, 실제 횟수={count}"
        )
    return content.replace(old, new, 1)


def update_formatters(content: str) -> tuple[str, bool]:
    changed = False

    if "# 커밋용\n" in content:
        content = replace_once(
            content,
            "# 커밋용\n",
            "",
            "formatters.py 임시 커밋 주석",
        )
        changed = True

    if NEW_HELPER not in content:
        if OLD_HELPER not in content:
            raise RuntimeError(
                "formatters.py의 기존 Range 포맷터를 찾지 못했습니다. "
                "PR #172 최신 브랜치인지 확인해 주세요."
            )
        content = replace_once(
            content,
            OLD_HELPER,
            NEW_HELPER,
            "formatters.py Range 포맷터",
        )
        changed = True

    return content, changed


def update_contracts(content: str) -> tuple[str, bool]:
    old = '    direction: Optional[str] = None\n'
    new = (
        '    direction: Literal["higher_is_better"] = '
        '"higher_is_better"\n'
    )

    if new in content:
        return content, False
    if old not in content:
        raise RuntimeError(
            "api_contracts.py의 MetricRangeResponse direction 필드를 찾지 못했습니다."
        )

    return replace_once(
        content,
        old,
        new,
        "api_contracts.py Range direction",
    ), True


def update_tests(content: str) -> tuple[str, bool]:
    changed = False
    import_line = (
        "from app.portfolio.formatters import "
        "build_metrics_payload  # noqa: E402\n"
    )
    import_anchor = (
        "from app.portfolio.tax_advice import "
        "calc_combined_tax_saving  # noqa: E402\n"
    )

    if import_line not in content:
        content = replace_once(
            content,
            import_anchor,
            import_anchor + import_line,
            "테스트 formatter import",
        )
        changed = True

    marker = "def test_metric_range_api_exposes_percent_only() -> None:"
    if marker not in content:
        content = content.rstrip() + TESTS_BLOCK + "\n"
        changed = True

    return content, changed


def main() -> int:
    root = find_repo_root(Path.cwd())
    paths = {
        root / FORMATTERS_PATH,
        root / CONTRACTS_PATH,
        root / TEST_PATH,
    }
    originals = {
        path: path.read_text(encoding="utf-8")
        for path in paths
    }

    formatters_path = root / FORMATTERS_PATH
    contracts_path = root / CONTRACTS_PATH
    test_path = root / TEST_PATH

    formatters, c1 = update_formatters(originals[formatters_path])
    contracts, c2 = update_contracts(originals[contracts_path])
    tests, c3 = update_tests(originals[test_path])

    updated = {
        formatters_path: formatters,
        contracts_path: contracts,
        test_path: tests,
    }

    if not any((c1, c2, c3)):
        print("[변경 없음] 이미 모두 반영되어 있습니다.")
        return 0

    try:
        for path, content in updated.items():
            compile(content, str(path), "exec")
            path.write_text(content, encoding="utf-8")
    except Exception as exc:
        for path, original in originals.items():
            path.write_text(original, encoding="utf-8")
        raise RuntimeError(
            "문법 검사에 실패해 모든 파일을 원본으로 되돌렸습니다."
        ) from exc

    print("[완료] PR #172 리뷰 후속 수정을 반영했습니다.")
    print("- 임시 '# 커밋용' 주석 제거")
    print("- Range는 프론트에 percent 값만 반환")
    print("- Range 원화 금액은 추가하지 않음")
    print("- 내부 monte_carlo_range_basis는 공식 metrics 응답에서 제외")
    print("- MDD direction은 higher_is_better로 계약에 명시")
    print("- 관련 오프라인 테스트 추가")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        raise SystemExit(1)
