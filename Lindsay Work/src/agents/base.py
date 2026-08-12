"""Shared harness for the three agents: caching, structured-output
validation, logging, and LIVE_AGENT / CACHED_AGENT / DETERMINISTIC_FALLBACK
mode tracking.

Every agent call goes through `AgentRunner.run`, which:
  1. Computes a cache key from the inputs + prompt version + model +
     taxonomy version (when relevant).
  2. Returns a cached result if present (mode = CACHED_AGENT for the run).
  3. Otherwise, if ANTHROPIC_API_KEY is configured, calls the live model,
     validates the JSON response against the given pydantic schema, and
     caches it (mode = LIVE_AGENT).
  4. Otherwise falls back to the deterministic function supplied by the
     caller (mode = DETERMINISTIC_FALLBACK). Fallback is never faked as a
     live call -- results are labeled and never silently blended.

Failures (malformed JSON, schema validation errors, API errors) are logged
without ever including the API key, and always fall back to the
deterministic path rather than crashing the pipeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from src.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, CACHE_DIR
from src.schema import ProcessingMode

logger = logging.getLogger("agents.base")

AGENT_CACHE_DIR = CACHE_DIR / "agent_cache"
AGENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

T = TypeVar("T", bound=BaseModel)


class AgentRunStats:
    """Tracks how many calls used each mode across a pipeline run."""

    def __init__(self) -> None:
        self.live_calls = 0
        self.cached_calls = 0
        self.fallback_calls = 0
        self.failed_live_calls = 0

    def overall_mode(self) -> ProcessingMode:
        if self.live_calls > 0:
            return ProcessingMode.LIVE_AGENT
        if self.cached_calls > 0:
            return ProcessingMode.CACHED_AGENT
        return ProcessingMode.DETERMINISTIC_FALLBACK

    def as_dict(self) -> dict:
        return {
            "live_calls": self.live_calls,
            "cached_calls": self.cached_calls,
            "fallback_calls": self.fallback_calls,
            "failed_live_calls": self.failed_live_calls,
            "overall_mode": self.overall_mode().value,
        }


def is_live_mode_available() -> bool:
    return bool(ANTHROPIC_API_KEY)


_client = None


def call_claude(system: str, user: str, max_tokens: int = 1024) -> str:
    """Call Claude and return the raw text response. Raises on any failure
    (caller's run_agent() catches and falls back). Never logs the API key."""
    global _client
    import anthropic

    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = _client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if hasattr(block, "text"))
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def cache_key(agent_name: str, payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    digest = hashlib.sha256(blob).hexdigest()[:24]
    return f"{agent_name}__{digest}"


def _cache_path(agent_name: str, key: str) -> Path:
    d = AGENT_CACHE_DIR / agent_name
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def read_cache(agent_name: str, key: str) -> dict | None:
    p = _cache_path(agent_name, key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cache read failed for %s: %s", p, exc)
        return None


def write_cache(agent_name: str, key: str, record: dict) -> None:
    p = _cache_path(agent_name, key)
    try:
        p.write_text(json.dumps(record, indent=2, default=str))
    except OSError as exc:
        logger.warning("Cache write failed for %s: %s", p, exc)


def run_agent(
    stats: AgentRunStats,
    agent_name: str,
    key_payload: dict,
    schema: type[T],
    live_fn: Callable[[], str] | None,
    fallback_fn: Callable[[], T],
) -> tuple[T, str]:
    """Returns (validated_result, mode) where mode is 'live' | 'cached' | 'fallback'."""
    key = cache_key(agent_name, key_payload)
    cached = read_cache(agent_name, key)
    if cached is not None:
        try:
            result = schema.model_validate(cached["output"])
            stats.cached_calls += 1
            return result, "cached"
        except ValidationError as exc:
            logger.warning("Cached result for %s failed schema validation, recomputing: %s", key, exc)

    if is_live_mode_available() and live_fn is not None:
        try:
            raw = live_fn()
            parsed = json.loads(raw)
            result = schema.model_validate(parsed)
            write_cache(agent_name, key, {"output": result.model_dump(mode="json"), "model": ANTHROPIC_MODEL, "source": "live"})
            stats.live_calls += 1
            return result, "live"
        except (json.JSONDecodeError, ValidationError, Exception) as exc:  # noqa: BLE001
            logger.warning("Live agent call failed for %s (%s), falling back to deterministic logic", agent_name, type(exc).__name__)
            stats.failed_live_calls += 1

    result = fallback_fn()
    write_cache(agent_name, key, {"output": result.model_dump(mode="json"), "model": "deterministic-fallback", "source": "fallback"})
    stats.fallback_calls += 1
    return result, "fallback"
