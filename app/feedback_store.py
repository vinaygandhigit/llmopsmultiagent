"""End-user feedback capture (Feedback loop gap #4).

Feedback is written twice: to LangSmith (as a `create_feedback` call attached
to the run_id, so it shows next to the trace in the LangSmith UI) and to a
local `feedback` table (durable even if LangSmith is unreachable, and easy to
query for the regression-dataset sync script). This is the "observe" step
that closes deploy -> observe -> evaluate -> improve -> redeploy: negative
feedback runs get pulled into a LangSmith "multiagentbank-regression"
dataset by scripts/sync_feedback_to_dataset.py so the next eval run and
prompt iteration are informed by real production failures.
"""
from __future__ import annotations

import logging

from langsmith import Client

from app.database import get_feedback_summary, get_negative_feedback_runs, insert_feedback
from app.guardrails import mask_pii
from app.langsmith_utils import resolve_project_id

logger = logging.getLogger("multiagentbank.feedback")

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client()
    return _client


def record_feedback(
    *, run_id: str, tenant_id: str, agent: str | None, score: float, comment: str | None = None
) -> None:
    """score is expected in [-1, 1] (thumbs down = -1, thumbs up = 1), but any
    float is accepted so this also works for a 1-5 star widget, etc.

    `comment` is free text a customer types, so unlike the structured
    account data the agents return (which is the legitimate business
    payload), it can incidentally contain PII (an email, a phone number they
    pasted in) that has no reason to be persisted or forwarded to a
    third-party observability platform verbatim - it's masked before either.
    """
    safe_comment = mask_pii(comment) if comment else comment
    insert_feedback(run_id=run_id, tenant_id=tenant_id, agent=agent, score=score, comment=safe_comment)

    try:
        client = _get_client()
        client.create_feedback(
            run_id=run_id,
            key="user_score",
            score=score,
            comment=safe_comment,
            session_id=resolve_project_id(client),
            source_info={"tenant_id": tenant_id, "agent": agent},
        )
    except Exception:
        logger.exception("Failed to push feedback to LangSmith for run_id=%s (kept locally).", run_id)


def feedback_summary() -> list[dict]:
    return [dict(row) for row in get_feedback_summary()]


def negative_feedback_runs(threshold: float = 0) -> list[dict]:
    return [dict(row) for row in get_negative_feedback_runs(threshold=threshold)]