"""LLM-as-judge faithfulness scoring for hallucination / quality drift
monitoring (Observability gap #1b).

Every agent turn is grounded in tool output (the ToolMessage content(s) in
the LangGraph result) - that's the "context" the final answer must be
faithful to. After each turn we ask a small, cheap judge model whether the
answer is actually supported by that context, log the score as LangSmith
feedback on the run (so it shows up next to the trace) and persist it in the
local quality_scores table, bucketed by time, so `/metrics/quality` can plot
a drift trend instead of a single point-in-time number.

Scoring is best-effort: any judge failure is swallowed so it never breaks the
user-facing response - this is a secondary monitoring signal, not a gate.
"""
from __future__ import annotations

import json
import logging
import random
import re

from langchain_anthropic import ChatAnthropic
from langsmith import Client

from app.config import JUDGE_MODEL, QUALITY_SCORING_ENABLED, QUALITY_SCORING_SAMPLE_RATE
from app.database import get_quality_drift, insert_quality_score
from app.langsmith_utils import resolve_project_id

logger = logging.getLogger("multiagentbank.quality")

_langsmith_client: Client | None = None


def _get_langsmith_client() -> Client:
    global _langsmith_client
    if _langsmith_client is None:
        _langsmith_client = Client()
    return _langsmith_client

_JUDGE_PROMPT = """You are a strict fact-checking judge for a banking assistant.

Given the CONTEXT (raw tool output the assistant had access to) and the
ANSWER the assistant gave to the customer's QUESTION, score how faithful the
answer is to the context - i.e. is every factual claim (numbers, statuses,
dates, names) in the answer actually supported by the context, with no
invented or unsupported details?

QUESTION:
{question}

CONTEXT (ground truth from bank systems):
{context}

ANSWER (to be checked):
{answer}

Respond with ONLY a JSON object, no other text:
{{"score": <float 0.0-1.0, 1.0 = fully grounded, 0.0 = fabricated>, "rationale": "<one sentence>"}}
"""

_judge_llm: ChatAnthropic | None = None


def _get_judge_llm() -> ChatAnthropic:
    global _judge_llm
    if _judge_llm is None:
        _judge_llm = ChatAnthropic(model=JUDGE_MODEL, temperature=0)
    return _judge_llm


def extract_context(messages: list) -> str:
    """Concatenate ToolMessage contents - the ground truth the answer must be faithful to.

    Public because evals/evaluators.py also needs this raw grounding text to
    evaluate an experiment run outside the live request path.
    """
    parts = []
    for message in messages:
        if type(message).__name__ == "ToolMessage":
            parts.append(str(message.content))
    return "\n".join(parts) if parts else "(no tool was called)"


def _parse_judge_response(raw: str) -> tuple[float, str]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    payload = json.loads(match.group(0) if match else raw)
    score = float(payload.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    return score, str(payload.get("rationale", ""))


def judge_faithfulness(question: str, context: str, answer: str) -> tuple[float, str] | None:
    """Core LLM-as-judge call, taking the grounding context as a plain
    string. Used both by score_faithfulness() below (live request path,
    which extracts context from LangChain messages) and directly by
    evals/evaluators.py (offline eval path, which already has context as a
    plain string from a target function's dict output).
    """
    try:
        judge = _get_judge_llm()
        response = judge.invoke(
            _JUDGE_PROMPT.format(question=question, context=context, answer=answer)
        )
        return _parse_judge_response(str(response.content))
    except Exception:
        logger.exception("Faithfulness scoring failed; continuing without a quality score.")
        return None


def score_faithfulness(question: str, messages: list, answer: str) -> tuple[float, str] | None:
    """Return (score, rationale) or None if scoring is disabled/skipped/fails."""
    if not QUALITY_SCORING_ENABLED:
        return None
    if QUALITY_SCORING_SAMPLE_RATE < 1.0 and random.random() > QUALITY_SCORING_SAMPLE_RATE:
        return None

    return judge_faithfulness(question, extract_context(messages), answer)


def record_quality_score(
    *,
    run_id: str | None,
    agent: str,
    question: str,
    messages: list,
    answer: str,
    session_id: str | None = None,
) -> tuple[float, str] | None:
    result = score_faithfulness(question, messages, answer)
    if result is None:
        return None
    score, rationale = result
    insert_quality_score(run_id=run_id, agent=agent, metric="faithfulness", score=score, rationale=rationale)

    if run_id:
        try:
            client = _get_langsmith_client()
            client.create_feedback(
                run_id=run_id, key="faithfulness", score=score, comment=rationale,
                session_id=session_id or resolve_project_id(client),
                source_info={"judge_model": JUDGE_MODEL},
            )
        except Exception:
            logger.exception("Failed to push faithfulness feedback to LangSmith for run_id=%s.", run_id)

    return result


def quality_drift(bucket: str = "day") -> list[dict]:
    return [dict(row) for row in get_quality_drift(bucket=bucket)]