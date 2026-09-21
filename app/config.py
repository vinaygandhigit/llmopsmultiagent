"""Central LLMOps configuration: pinned model versions, cost table, SLOs,
rate limits, and guardrail toggles. Single source of truth so behavior
changes are visible in one place instead of scattered magic numbers.
"""
import os

# --- Model version pinning -------------------------------------------------
# Pin exact, dated model snapshots (not floating aliases like "latest") so an
# upstream model upgrade can't silently change agent behavior. Bump these
# deliberately, re-run the eval suite (see evals/run_evals.py), and only then
# promote.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Cheap/fast model used for automated LLM-as-judge quality scoring so scoring
# cost stays small relative to the primary agent call.
JUDGE_MODEL = os.getenv("LLMOPS_JUDGE_MODEL", "claude-haiku-4-5-20251001")

# --- Approximate cost table (USD per 1M tokens) -----------------------------
# For demo/observability purposes only - not billing-accurate. Update if
# provider pricing changes.
COST_PER_MILLION_TOKENS = {
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}
DEFAULT_COST = {"input": 3.00, "output": 15.00}

# --- Guardrails --------------------------------------------------------------
GUARDRAILS_ENABLED = os.getenv("GUARDRAILS_ENABLED", "true").strip().lower() in ("true", "1", "yes")

# --- Cost controls / rate limiting ------------------------------------------
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
DAILY_TOKEN_BUDGET_PER_TENANT = int(os.getenv("DAILY_TOKEN_BUDGET_PER_TENANT", "50000"))

# --- Latency SLO -------------------------------------------------------------
LATENCY_SLO_MS = int(os.getenv("LATENCY_SLO_MS", "8000"))

# --- Quality / hallucination drift monitoring -------------------------------
QUALITY_SCORING_ENABLED = os.getenv("QUALITY_SCORING_ENABLED", "true").strip().lower() in ("true", "1", "yes")
# Score every Nth request to control judge-model cost in higher-traffic setups.
QUALITY_SCORING_SAMPLE_RATE = float(os.getenv("QUALITY_SCORING_SAMPLE_RATE", "1.0"))

DEFAULT_TENANT_ID = "anonymous"


def cost_for_usage(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_MILLION_TOKENS.get(model, DEFAULT_COST)
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]