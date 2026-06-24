from typing import Literal


IPS_SOURCE_TYPE = Literal["initial", "consultation"]
IPS_KEYS = (
    "Goal",
    "Asset",
    "Return",
    "Risk",
    "Time",
    "Tax",
    "Liquidity",
    "Legal",
    "Unique",
)


def flatten_ips_json(raw_ips_json: dict) -> dict:
    if not isinstance(raw_ips_json, dict):
        raise ValueError("IPS JSON은 객체여야 합니다.")

    rrttllu = raw_ips_json.get("RRTTLLU")
    if rrttllu is None:
        return _validate_flat_ips_json(raw_ips_json)

    if not isinstance(rrttllu, dict):
        raise ValueError("IPS JSON의 RRTTLLU 필드는 객체여야 합니다.")

    flattened = {
        "Goal": raw_ips_json.get("Goal"),
        "Asset": raw_ips_json.get("Asset"),
    }
    flattened.update(rrttllu)
    return _validate_flat_ips_json(flattened)


def build_ips_snapshot_payload(
    *,
    client_id: str,
    consultation_id: str | None,
    source_type: IPS_SOURCE_TYPE,
    raw_ips_json: dict,
) -> dict:
    ips_json = _validate_flat_ips_json(raw_ips_json)

    return {
        "client_id": client_id,
        "consultation_id": consultation_id,
        "source_type": source_type,
        "goal": ips_json.get("Goal"),
        "asset": _normalize_number(ips_json.get("Asset"), "Asset"),
        "return": _normalize_number(ips_json.get("Return"), "Return"),
        "risk": ips_json.get("Risk"),
        "time": _normalize_number(ips_json.get("Time"), "Time"),
        "tax": ips_json.get("Tax"),
        "liquidity": ips_json.get("Liquidity"),
        "legal": ips_json.get("Legal"),
        "unique": ips_json.get("Unique"),
        "raw_ips_json": ips_json,
    }


def fill_missing_ips_values(raw_ips_json: dict, fallback_ips_json: dict | None) -> dict:
    """raw_ips_json의 미발화 값(None/빈 문자열)을 fallback IPS 값으로 채운다.

    STT 추출은 고객 발화에 없는 항목을 null로 반환할 수 있다. 상담 IPS 스냅샷과
    포트폴리오 계산 입력에는 9개 값이 최대한 채워져 있어야 하므로, 고객의 최초
    IPS(initial)를 보수적 fallback으로 사용한다.
    """
    ips_json = flatten_ips_json(raw_ips_json)
    if not fallback_ips_json:
        return ips_json

    fallback = flatten_ips_json(fallback_ips_json)
    return {
        key: (
            fallback.get(key)
            if _is_missing_ips_value(ips_json.get(key))
            else ips_json.get(key)
        )
        for key in IPS_KEYS
    }


def _validate_flat_ips_json(raw_ips_json: dict) -> dict:
    missing_keys = [key for key in IPS_KEYS if key not in raw_ips_json]
    if missing_keys:
        raise ValueError(f"IPS JSON에 필수 키가 없습니다: {', '.join(missing_keys)}")

    return {key: raw_ips_json.get(key) for key in IPS_KEYS}


def _is_missing_ips_value(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_number(value: int | float | str | None, field_name: str) -> int | float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} 값은 숫자여야 합니다.")

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        try:
            return float(stripped)
        except ValueError as exc:
            raise ValueError(f"{field_name} 값은 숫자여야 합니다.") from exc

    raise ValueError(f"{field_name} 값은 숫자여야 합니다.")
