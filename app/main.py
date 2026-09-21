"""FastAPI app exposing the multiagent bank assistant, instrumented end to
end for LLMOps: guardrails, per-tenant rate/cost limits, LangSmith tracing +
feedback, token/cost/quality metrics, and prompt version visibility.
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.agent import AGENT_NAME, AgentRunResult, run_multi_agent
from app.config import DEFAULT_TENANT_ID, LATENCY_SLO_MS
from app.database import get_balance_by_account_number, get_guardrail_summary, init_llmops_tables
from app.feedback_store import feedback_summary, negative_feedback_runs, record_feedback
from app.guardrails import GuardrailBlocked, enforce_input
from app.prompts import get_history, get_manifest_snapshot
from app.quality import quality_drift
from app.rate_limiter import RateLimitExceeded, TokenBudgetExceeded, check_and_record_request, check_token_budget
from app.usage import usage_summary

logger = logging.getLogger("multiagentbank")

app = FastAPI(title="Multiagent Bank - LLMOps Reference API")


def _langsmith_tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "false").strip().lower() in ("true", "1", "yes")


@app.on_event("startup")
def _startup() -> None:
    init_llmops_tables()
    if _langsmith_tracing_enabled():
        project = os.getenv("LANGSMITH_PROJECT", "default")
        logger.info("LangSmith tracing enabled (project=%s).", project)
    else:
        logger.info(
            "LangSmith tracing disabled. Set LANGSMITH_TRACING=true and "
            "LANGSMITH_API_KEY to enable monitoring at smith.langchain.com."
        )


def get_tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    """Tenant/user identity for rate limiting, cost attribution, and feedback.

    In this demo it's a plain header the caller sets; a real deployment would
    derive it from an authenticated principal (API key, JWT subject, etc).
    """
    return (x_tenant_id or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    agent: str
    reply: str
    run_id: str | None
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    faithfulness_score: float | None
    latency_slo_breached: bool


class FeedbackRequest(BaseModel):
    run_id: str
    score: float  # e.g. +1 thumbs up, -1 thumbs down, or any float scale
    agent: str | None = None
    comment: str | None = None


def _to_response(result: AgentRunResult) -> ChatResponse:
    return ChatResponse(
        agent=result.agent,
        reply=result.reply,
        run_id=result.run_id,
        model=result.model,
        prompt_version=result.prompt_version,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        faithfulness_score=result.faithfulness_score,
        latency_slo_breached=result.latency_ms > LATENCY_SLO_MS,
    )


def _run_guarded(agent_fn, message: str, tenant_id: str, agent_label: str) -> ChatResponse:
    """Shared guardrail -> rate-limit -> budget -> agent pipeline for every
    chat endpoint, so each one enforces the same production controls."""
    try:
        enforce_input(message, tenant_id=tenant_id, agent=agent_label)
    except GuardrailBlocked as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        check_and_record_request(tenant_id)
        check_token_budget(tenant_id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except TokenBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    result = agent_fn(message, tenant_id=tenant_id)
    if result.latency_ms > LATENCY_SLO_MS:
        logger.warning(
            "Latency SLO breached: agent=%s tenant=%s latency_ms=%.0f (SLO=%dms)",
            result.agent, tenant_id, result.latency_ms, LATENCY_SLO_MS,
        )
    return _to_response(result)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "langsmith_tracing": _langsmith_tracing_enabled(),
        "langsmith_project": os.getenv("LANGSMITH_PROJECT") if _langsmith_tracing_enabled() else None,
    }


@app.post("/chat", response_model=ChatResponse)
def chat_with_bank_supervisor(request: ChatRequest, tenant_id: str = Depends(get_tenant_id)) -> ChatResponse:
    """Single entry point for every conversational request. The
    bank_supervisor's own LLM decides which specialist agent(s) to call
    (account/transaction/service) - callers never pick an agent themselves.
    """
    return _run_guarded(run_multi_agent, request.message, tenant_id, AGENT_NAME)


@app.get("/account-agent/balance/{account_number}")
def balance_enquiry_direct(account_number: str) -> dict:
    """Direct (non-LLM) balance enquiry endpoint for quick testing of the underlying tool/data."""
    record = get_balance_by_account_number(account_number.strip().upper())
    if record is None:
        raise HTTPException(status_code=404, detail=f"No account found with account number '{account_number}'.")
    return dict(record)


# --- Feedback loop (gap #4) --------------------------------------------------

@app.post("/feedback")
def submit_feedback(request: FeedbackRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Capture end-user thumbs up/down (or any numeric signal) against a
    specific run_id returned by POST /chat. Pushed to LangSmith
    (visible next to the trace) and stored locally; negative feedback becomes
    a candidate for the "multiagentbank-regression" LangSmith dataset via
    scripts/sync_feedback_to_dataset.py, closing the observe -> evaluate loop.
    """
    record_feedback(run_id=request.run_id, tenant_id=tenant_id, agent=request.agent, score=request.score, comment=request.comment)
    return {"status": "recorded"}


@app.get("/feedback/summary")
def feedback_summary_endpoint() -> dict:
    return {"by_agent": feedback_summary(), "negative_runs": negative_feedback_runs()}


# --- Observability metrics (gap #1) -----------------------------------------

@app.get("/metrics/usage")
def usage_metrics() -> dict:
    """Token usage and estimated cost, aggregated per agent/model."""
    return {"by_agent_model": usage_summary()}


@app.get("/metrics/quality")
def quality_metrics(bucket: str = "day") -> dict:
    """Rolling faithfulness score over time - the hallucination/drift trend."""
    if bucket not in ("day", "hour"):
        raise HTTPException(status_code=400, detail="bucket must be 'day' or 'hour'")
    return {"bucket": bucket, "drift": quality_drift(bucket=bucket)}


@app.get("/metrics/guardrails")
def guardrail_metrics() -> dict:
    return {"events": [dict(row) for row in get_guardrail_summary()]}


# --- Prompt & model versioning (gap #3) --------------------------------------

@app.get("/prompts")
def prompts_status() -> dict:
    """Current prod prompt version per agent, plus promotion/rollback history."""
    return {"manifest": get_manifest_snapshot(), "history": get_history()}