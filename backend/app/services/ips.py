from typing import Literal


IPS_SOURCE_TYPE = Literal["initial", "consultation"]


def flatten_ips_json(raw_ips_json: dict) -> dict:
    rrttllu = raw_ips_json.get("RRTTLLU")
    if not isinstance(rrttllu, dict):
        return raw_ips_json

    flattened = {
        "Goal": raw_ips_json.get("Goal"),
        "Asset": raw_ips_json.get("Asset"),
    }
    flattened.update(rrttllu)
    return flattened


def build_ips_snapshot_payload(
    *,
    client_id: str,
    consultation_id: str | None,
    source_type: IPS_SOURCE_TYPE,
    raw_ips_json: dict,
) -> dict:
    return {
        "client_id": client_id,
        "consultation_id": consultation_id,
        "source_type": source_type,
        "goal": raw_ips_json.get("Goal"),
        "asset": raw_ips_json.get("Asset"),
        "return": raw_ips_json.get("Return"),
        "risk": raw_ips_json.get("Risk"),
        "time": raw_ips_json.get("Time"),
        "tax": raw_ips_json.get("Tax"),
        "liquidity": raw_ips_json.get("Liquidity"),
        "legal": raw_ips_json.get("Legal"),
        "unique": raw_ips_json.get("Unique"),
        "raw_ips_json": raw_ips_json,
    }
