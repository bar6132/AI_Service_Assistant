"""OpenAI-compatible client + provider chain. Source: design doc section 12
(lines 293-311) and the model-related row of section 16 (lines 378-381)."""

import json
import logging
import os
import time
from typing import TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("agent")

# Per-HTTP-call timeout. The SDK's own retries are switched off (max_retries=0
# in _client) so this chain is the only retry policy: per provider at most 2
# calls, so the worst case is 2 x timeout + backoff before failing over.
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
TRANSIENT_BACKOFF_SECONDS = 1.0

KNOWN_PROVIDERS = ("local", "grok", "gemini")
DEFAULT_PROVIDERS = "gemini"  # the only provider the 10 test cases ran against
REPAIR_SUFFIX = "\n\nהפלט הקודם לא תאם לסכמה. החזר JSON תקין בלבד, לפי הסכמה, בלי טקסט נוסף."


class ConfigError(Exception):
    """PROVIDERS / API keys are misconfigured. Raised before any customer
    request is handled, instead of silently escalating everything."""

# Endpoints per design line 297-301. Model names/versions are not specified
# verbatim in the source ("Fast" for Grok, "Flash-Lite" for Gemini) — the
# exact ids below are my choice, overridable via env (see progress doc).
# Read lazily (function, not a module-level dict) so it always sees whatever
# was loaded by load_dotenv() at CLI startup, regardless of import order, and
# so an empty string in .env (XAI_MODEL=) falls back to the default instead
# of overriding it (`or`, not getenv's own default arg).
def _provider_config(provider: str) -> dict:
    if provider == "local":
        return {
            "base_url": os.getenv("LOCAL_BASE_URL") or "http://localhost:8080/v1",
            "api_key": "not-needed",
            "model": os.getenv("LOCAL_MODEL") or "local-model",
        }
    if provider == "grok":
        return {
            "base_url": "https://api.x.ai/v1",
            "api_key": os.getenv("XAI_API_KEY") or "",
            "model": os.getenv("XAI_MODEL") or "grok-4-fast",
        }
    if provider == "gemini":
        return {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": os.getenv("GEMINI_API_KEY") or "",
            "model": os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite",
        }
    raise ValueError(f"unknown provider: {provider}")


class AllProvidersFailed(Exception):
    """Whole provider chain failed. Caller must escalate — design line 308:
    "אם כולם נכשלים → escalate בטוח"."""


def _provider_chain() -> list[str]:
    raw = os.getenv("PROVIDERS") or DEFAULT_PROVIDERS
    names = [p.strip().lower() for p in raw.split(",") if p.strip()]
    unknown = [n for n in names if n not in KNOWN_PROVIDERS]
    if unknown:
        raise ConfigError(
            f"unknown provider(s) in PROVIDERS: {', '.join(unknown)} "
            f"(supported: {', '.join(KNOWN_PROVIDERS)})"
        )
    return names


def _usable_providers() -> list[tuple[str, dict]]:
    usable = []
    for name in _provider_chain():
        cfg = _provider_config(name)
        if name != "local" and not cfg["api_key"]:
            logger.warning("llm.config provider=%s skipped=no_api_key", name)
            continue
        usable.append((name, cfg))
    return usable


def validate_config() -> list[str]:
    """Fail fast at startup: returns the usable provider names or raises."""
    usable = _usable_providers()
    if not usable:
        raise ConfigError(
            "no usable model provider: set PROVIDERS (e.g. gemini) and the matching "
            "API key (GEMINI_API_KEY / XAI_API_KEY) in .env"
        )
    return [name for name, _ in usable]


def _client(cfg: dict) -> OpenAI:
    return OpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"] or "unset",
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def _call_structured(client: OpenAI, model: str, system: str, user: str, schema_model: type[T]) -> T:
    response = client.chat.completions.create(
        model=model,
        temperature=0,  # design line 305: "temperature=0 בכל הקריאות"
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_model.__name__,
                "schema": schema_model.model_json_schema(),
                "strict": True,
            },
        },
    )
    raw = response.choices[0].message.content
    return schema_model.model_validate_json(raw)


def _no_provider_message(last_error: Exception | None) -> str:
    return str(last_error) if last_error else "no usable provider configured"


def run_structured(system: str, user: str, schema_model: type[T]) -> T:
    """Design line 308: "כל ספק מקבל ניסיון אחד + ניסיון תיקון. אחר כך עוברים
    לספק הבא". Per provider, at most 2 calls: a schema error gets a repair
    prompt (design line 380); a transient transport error (timeout, 429, 5xx)
    gets one plain retry after a short backoff; a permanent error (401/400)
    moves straight to the next provider (design line 381).
    """
    last_error: Exception | None = None
    for provider, cfg in _usable_providers():
        client = _client(cfg)
        prompt = user
        for attempt_num in (1, 2):
            t0 = time.monotonic()
            try:
                result = _call_structured(client, cfg["model"], system, prompt, schema_model)
            except (ValidationError, json.JSONDecodeError) as exc:
                logger.warning(
                    "llm.structured provider=%s model=%s attempt=%d ms=%d outcome=schema_error",
                    provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000,
                )
                last_error = exc
                prompt = user + REPAIR_SUFFIX
                continue
            except Exception as exc:  # noqa: BLE001 - provider unreachable / timeout / rate limit
                logger.warning(
                    "llm.structured provider=%s model=%s attempt=%d ms=%d outcome=transport_error error=%s",
                    provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000, type(exc).__name__,
                )
                last_error = exc
                if attempt_num == 1 and _is_transient(exc):
                    time.sleep(TRANSIENT_BACKOFF_SECONDS)
                    continue
                break
            logger.info(
                "llm.structured provider=%s model=%s attempt=%d ms=%d outcome=ok",
                provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000,
            )
            return result
    raise AllProvidersFailed(_no_provider_message(last_error))


def run_text(system: str, user: str) -> str:
    """Free-text completion for LLM #2 (reply composition, design line 132).
    Not in the design's explicit list of functions — added because structured
    extraction (run_structured) and natural-language composition need
    different call shapes; same provider chain and temperature=0 apply to
    both (design lines 295, 305)."""
    last_error: Exception | None = None
    for provider, cfg in _usable_providers():
        client = _client(cfg)
        for attempt_num in (1, 2):  # empty reply or transient error gets one retry
            t0 = time.monotonic()
            try:
                response = client.chat.completions.create(
                    model=cfg["model"],
                    temperature=0,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    logger.info(
                        "llm.text provider=%s model=%s attempt=%d ms=%d outcome=ok",
                        provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000,
                    )
                    return text
                last_error = ValueError("empty completion")
                logger.warning(
                    "llm.text provider=%s model=%s attempt=%d ms=%d outcome=empty",
                    provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "llm.text provider=%s model=%s attempt=%d ms=%d outcome=transport_error error=%s",
                    provider, cfg["model"], attempt_num, (time.monotonic() - t0) * 1000, type(exc).__name__,
                )
                last_error = exc
                if attempt_num == 1 and _is_transient(exc):
                    time.sleep(TRANSIENT_BACKOFF_SECONDS)
                    continue
                break
    raise AllProvidersFailed(_no_provider_message(last_error))
