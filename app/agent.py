"""Configurable Gemini- or Claude-powered banking agents, instrumented for
LLMOps: versioned prompts (app.prompts), per-request token/cost tracking
(app.usage), LangSmith run-id propagation for feedback (app.feedback_store),
and LLM-as-judge faithfulness scoring for hallucination/drift monitoring
(app.quality).
"""
from __future__ import annotations

import contextvars
import os
import time
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app import quality
from app import usage as usage_module
from app.config import ANTHROPIC_MODEL, DEFAULT_TENANT_ID, GEMINI_MODEL
from app.prompts import current_version, get_prompt
from app.tools import (
    address_update,
    balance_enquiry,
    cheque_book_update_status,
    kyc_update_status,
    statement_details,
    transaction_details,
)

ACCOUNT_AGENT_NAME = "account_agent"
TRANSACTION_AGENT_NAME = "transaction_agent"
SERVICE_AGENT_NAME = "service_agent"
AGENT_NAME = "bank_supervisor"

_SPECIALIST_AGENTS = {ACCOUNT_AGENT_NAME, TRANSACTION_AGENT_NAME, SERVICE_AGENT_NAME}

SCOPE_NOTE = (
    " The customer's message may also mention other banking topics outside your "
    "scope (e.g. balances, transactions, statements, address/KYC/cheque book "
    "services) — a separate specialist agent handles those in parallel, and their "
    "answer will be combined with yours automatically. Do NOT mention, apologize "
    "for, or refer to topics outside your scope in any way. Answer only the part "
    "of the request that falls within your scope, as if that were the entire "
    "question."
)

# Propagates the caller's tenant id into the @tool wrapper functions below,
# which the LLM invokes with only a `message` argument (their schema is
# generated from the function signature, so we can't add a tenant_id param
# there without also exposing/confusing it to the model). Set once per
# request in run_multi_agent(); read by the tool wrappers via _current_tenant_id.get().
_current_tenant_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_tenant_id", default=DEFAULT_TENANT_ID
)

# agent_key -> (prompt_version, model_id, compiled_agent). Keying the cache on
# prompt_version and model_id means promoting/rolling back a prompt
# (app.prompts.promote/rollback) or changing LLM_PROVIDER/*_MODEL takes effect
# on the very next request - no restart needed to roll back a bad prompt.
_agents: dict[str, tuple[str, str, object]] = {}
_supervisor_cache: tuple[str, str, object] | None = None


@dataclass
class AgentRunResult:
    """Everything an API layer needs to report on one agent turn: the reply
    plus the LLMOps metadata (which prompt/model produced it, what it cost,
    how long it took, and how faithful it was judged to be)."""

    reply: str
    agent: str
    run_id: str | None
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    faithfulness_score: float | None = None
    context: str = ""


def _get_llm() -> ChatAnthropic | ChatGoogleGenerativeAI:
    provider = os.getenv("LLM_PROVIDER", "claude").strip().lower()

    if provider == "claude":
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", ANTHROPIC_MODEL),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", GEMINI_MODEL),
            google_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        )

    raise ValueError("Unsupported LLM_PROVIDER. Choose 'claude' or 'gemini'.")


def _model_identifier(llm: ChatAnthropic | ChatGoogleGenerativeAI) -> str:
    return getattr(llm, "model", None) or getattr(llm, "model_name", None) or "unknown"


def get_agent(agent_key: str):
    """Lazily build and cache one of the three specialist agents."""
    configurations = {
        ACCOUNT_AGENT_NAME: [balance_enquiry],
        TRANSACTION_AGENT_NAME: [transaction_details, statement_details],
        SERVICE_AGENT_NAME: [address_update, kyc_update_status, cheque_book_update_status],
    }
    try:
        tools = configurations[agent_key]
    except KeyError as exc:
        raise ValueError(f"Unknown agent: {agent_key}") from exc

    prompt_version = current_version(agent_key)
    llm = _get_llm()
    model_id = _model_identifier(llm)

    cached = _agents.get(agent_key)
    if cached and cached[0] == prompt_version and cached[1] == model_id:
        return cached[2]

    prompt_text = get_prompt(agent_key, version=prompt_version).text + SCOPE_NOTE
    compiled = create_agent(model=llm, tools=tools, system_prompt=prompt_text)
    _agents[agent_key] = (prompt_version, model_id, compiled)
    return compiled


def get_supervisor():
    """Lazily build and cache the supervisor that routes to specialist agents."""
    global _supervisor_cache

    prompt_version = current_version(AGENT_NAME)
    llm = _get_llm()
    model_id = _model_identifier(llm)

    if (
        _supervisor_cache
        and _supervisor_cache[0] == prompt_version
        and _supervisor_cache[1] == model_id
    ):
        return _supervisor_cache[2]

    prompt_text = get_prompt(AGENT_NAME, version=prompt_version).text
    compiled = create_agent(
        model=llm,
        tools=[account_agent, transaction_agent, service_agent],
        system_prompt=prompt_text,
    )
    _supervisor_cache = (prompt_version, model_id, compiled)
    return compiled


def _run_agent(agent_key: str, message: str, tenant_id: str) -> AgentRunResult:
    prompt_version = current_version(agent_key)
    model_id = _model_identifier(_get_llm())

    started = time.perf_counter()
    result = get_agent(agent_key).invoke({"messages": [{"role": "user", "content": message}]})
    latency_ms = (time.perf_counter() - started) * 1000

    messages = result["messages"]
    reply = messages[-1].content

    run_tree = get_current_run_tree()
    run_id = str(run_tree.id) if run_tree else None
    session_id = str(run_tree.session_id) if run_tree and run_tree.session_id else None

    usage = usage_module.extract_usage(messages)
    cost_usd = usage_module.record_usage(
        run_id=run_id,
        tenant_id=tenant_id,
        agent=agent_key,
        model=model_id,
        prompt_version=prompt_version,
        usage=usage,
        latency_ms=latency_ms,
    )

    quality_result = quality.record_quality_score(
        run_id=run_id, agent=agent_key, question=message, messages=messages, answer=reply,
        session_id=session_id,
    )

    return AgentRunResult(
        reply=reply,
        agent=agent_key,
        run_id=run_id,
        model=model_id,
        prompt_version=prompt_version,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        faithfulness_score=quality_result[0] if quality_result else None,
        context=quality.extract_context(messages),
    )


@traceable(name=ACCOUNT_AGENT_NAME, run_type="chain", tags=["specialist", "account"])
def run_account_agent(message: str, tenant_id: str | None = None) -> AgentRunResult:
    return _run_agent(ACCOUNT_AGENT_NAME, message, tenant_id or _current_tenant_id.get())


@traceable(name=TRANSACTION_AGENT_NAME, run_type="chain", tags=["specialist", "transaction"])
def run_transaction_agent(message: str, tenant_id: str | None = None) -> AgentRunResult:
    return _run_agent(TRANSACTION_AGENT_NAME, message, tenant_id or _current_tenant_id.get())


@traceable(name=SERVICE_AGENT_NAME, run_type="chain", tags=["specialist", "service"])
def run_service_agent(message: str, tenant_id: str | None = None) -> AgentRunResult:
    return _run_agent(SERVICE_AGENT_NAME, message, tenant_id or _current_tenant_id.get())


@tool
def account_agent(message: str) -> str:
    """Delegate an account balance or account details request."""
    return run_account_agent(message).reply


@tool
def transaction_agent(message: str) -> str:
    """Delegate a transaction history or statement request."""
    return run_transaction_agent(message).reply


@tool
def service_agent(message: str) -> str:
    """Delegate an address, KYC, or cheque book service request."""
    return run_service_agent(message).reply


def _run_supervisor(message: str, tenant_id: str) -> AgentRunResult:
    prompt_version = current_version(AGENT_NAME)
    model_id = _model_identifier(_get_llm())

    started = time.perf_counter()
    result = get_supervisor().invoke({"messages": [{"role": "user", "content": message}]})
    latency_ms = (time.perf_counter() - started) * 1000

    messages = result["messages"]
    reply = messages[-1].content

    run_tree = get_current_run_tree()
    run_id = str(run_tree.id) if run_tree else None
    session_id = str(run_tree.session_id) if run_tree and run_tree.session_id else None

    usage = usage_module.extract_usage(messages)
    cost_usd = usage_module.record_usage(
        run_id=run_id,
        tenant_id=tenant_id,
        agent=AGENT_NAME,
        model=model_id,
        prompt_version=prompt_version,
        usage=usage,
        latency_ms=latency_ms,
    )

    quality_result = quality.record_quality_score(
        run_id=run_id, agent=AGENT_NAME, question=message, messages=messages, answer=reply,
        session_id=session_id,
    )

    return AgentRunResult(
        reply=reply,
        agent=AGENT_NAME,
        run_id=run_id,
        model=model_id,
        prompt_version=prompt_version,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        faithfulness_score=quality_result[0] if quality_result else None,
        context=quality.extract_context(messages),
    )


@traceable(name=AGENT_NAME, run_type="chain", tags=["supervisor"])
def run_multi_agent(message: str, tenant_id: str = DEFAULT_TENANT_ID) -> AgentRunResult:
    """Always delegate to the bank_supervisor's own LLM routing - it decides
    which specialist(s) to call (including calling several for a multi-topic
    request), rather than a keyword heuristic here second-guessing it.
    LangGraph's tool node already executes multiple tool calls from one LLM
    turn concurrently, so multi-topic requests aren't sequential just because
    there's no manual thread-pool branch here anymore.
    """
    token = _current_tenant_id.set(tenant_id)
    try:
        return _run_supervisor(message, tenant_id)
    finally:
        _current_tenant_id.reset(token)