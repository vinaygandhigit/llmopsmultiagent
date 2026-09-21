"""Token usage and cost tracking per agent request (Observability gap #1a).

LangSmith already captures token counts per LLM call inside a trace, but
those numbers aren't queryable as a time series without going through the
LangSmith API. This module extracts usage from the LangGraph result,
estimates cost, and persists it locally (usage_metrics table) so `/metrics/usage`
can serve aggregate dashboards without round-tripping to LangSmith.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import LATENCY_SLO_MS, cost_for_usage
from app.database import get_usage_summary, insert_usage_metric


@dataclass
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "UsageInfo") -> "UsageInfo":
        return UsageInfo(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


def extract_usage(messages: list) -> UsageInfo:
    """Sum usage_metadata across every AIMessage in a LangGraph result.

    A single agent turn can involve multiple LLM calls (one per tool-calling
    round-trip), so this is not just the last message's usage.
    """
    usage = UsageInfo()
    for message in messages:
        metadata = getattr(message, "usage_metadata", None)
        if not metadata:
            continue
        usage = usage + UsageInfo(
            input_tokens=metadata.get("input_tokens", 0),
            output_tokens=metadata.get("output_tokens", 0),
            total_tokens=metadata.get("total_tokens", 0),
        )
    return usage


def record_usage(
    *,
    run_id: str | None,
    tenant_id: str,
    agent: str,
    model: str,
    prompt_version: str | None,
    usage: UsageInfo,
    latency_ms: float,
) -> float:
    """Persist a usage row, return the estimated cost in USD."""
    cost_usd = cost_for_usage(model, usage.input_tokens, usage.output_tokens)
    slo_breached = latency_ms > LATENCY_SLO_MS
    insert_usage_metric(
        run_id=run_id,
        tenant_id=tenant_id,
        agent=agent,
        model=model,
        prompt_version=prompt_version,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        slo_breached=slo_breached,
    )
    return cost_usd


def usage_summary() -> list[dict]:
    return [dict(row) for row in get_usage_summary()]