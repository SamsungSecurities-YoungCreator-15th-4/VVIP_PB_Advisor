# ruff: noqa: E501
"""Unique/Tax 의미 해석 LLM의 공용 인프라.

도메인 스키마·프롬프트·결과는 Unique와 Tax 모듈에서 완전히 분리한다.
이 파일은 Azure 클라이언트, 민감정보 마스킹, 문자열 정규화처럼
도메인에 무관한 기능만 제공한다.
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from typing import Any, Dict

from app.core.azure_openai import build_azure_client


SEMANTIC_MAX_INPUT_CHARS = 6_000


@lru_cache(maxsize=1)
def get_semantic_client():
    """기존 Azure 공용 endpoint/key를 재사용하는 의미 해석용 클라이언트."""

    api_version = os.getenv(
        "AZURE_OPENAI_SEMANTIC_API_VERSION",
        os.getenv("AZURE_OPENAI_LLM_API_VERSION", "2025-01-01-preview"),
    )
    return build_azure_client(api_version)


def get_semantic_deployment() -> str:
    """별도 배포명이 없으면 기존 AI 인사이트 LLM 배포를 재사용한다."""

    return os.getenv(
        "AZURE_OPENAI_SEMANTIC_DEPLOYMENT",
        os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", "ai-insight-llm"),
    )


def get_semantic_seed() -> int:
    raw = os.getenv("PORTFOLIO_SEMANTIC_LLM_SEED", "42")
    try:
        return int(raw)
    except ValueError:
        return 42


def env_enabled(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def stringify_natural_language(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " | ".join(
            f"{key}: {stringify_natural_language(item)}" for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return " | ".join(stringify_natural_language(item) for item in value)
    return str(value)


def normalize_semantic_text(value: Any) -> str:
    """의미는 유지하면서 공백만 안정적으로 정규화한다."""

    text = stringify_natural_language(value).strip()[:SEMANTIC_MAX_INPUT_CHARS]
    text = re.sub(r"[\t\r ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def mask_sensitive_text(text: str) -> str:
    """포트폴리오 해석에 필요하지 않은 직접 식별정보를 Azure 전송 전에 마스킹한다.

    금액 숫자는 계산에 필요하므로 일반적인 장문 숫자를 무조건 지우지 않는다.
    이메일·전화번호·주민등록번호·명시된 계좌/카드번호만 대상으로 한다.
    """

    masked = text
    masked = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL]",
        masked,
    )
    masked = re.sub(
        r"(?<!\d)(?:01[016789])[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)",
        "[PHONE]",
        masked,
    )
    masked = re.sub(
        r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)",
        "[RESIDENT_ID]",
        masked,
    )
    masked = re.sub(
        r"((?:계좌(?:번호)?|카드(?:번호)?)\s*[:=]?\s*)[0-9-]{8,24}",
        r"\1[ACCOUNT_ID]",
        masked,
        flags=re.IGNORECASE,
    )
    return masked


def stable_hash(*parts: str) -> str:
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def extract_message_content(response: Any) -> str:
    if not getattr(response, "choices", None):
        raise ValueError("의미 해석 LLM 응답에 choices가 없습니다.")
    content = response.choices[0].message.content
    if not content or not str(content).strip():
        raise ValueError("의미 해석 LLM이 빈 응답을 반환했습니다.")
    return str(content).strip()


def create_structured_completion(
    *,
    schema_name: str,
    schema: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
):
    """temperature=0 + 고정 seed + strict JSON schema로 호출한다.

    일부 Azure 배포에서 seed를 지원하지 않는 경우에만 seed 없이 한 번 재시도한다.
    원문·키·endpoint는 예외 메시지에 포함하지 않는다.
    """

    client = get_semantic_client()
    kwargs = {
        "model": get_semantic_deployment(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        "seed": get_semantic_seed(),
    }

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        message = str(exc).lower()
        if "seed" not in message or not any(
            token in message for token in ("unsupported", "not supported", "unknown")
        ):
            raise
        kwargs.pop("seed", None)
        return client.chat.completions.create(**kwargs)
