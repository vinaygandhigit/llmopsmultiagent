"""Input/output guardrails: prompt-injection heuristics and PII masking.

Scope note: this is a banking assistant, so account numbers, balances,
addresses, and customer names are the legitimate business data the agent is
supposed to return to the account holder - they must NOT be redacted from the
actual API response. The guardrail here therefore does two different things:

1. Blocks obviously malicious input (prompt-injection / instruction-override
   attempts) before it reaches the LLM.
2. Masks PII-shaped substrings (emails, phone numbers, card numbers, national
   ID numbers) before that text is attached to LangSmith trace metadata or
   local logs/metrics - so the audit trail sent to a third-party observability
   platform doesn't carry raw PII, even though the user-facing answer is
   unmasked and correct.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import GUARDRAILS_ENABLED
from app.database import insert_guardrail_event

# --- Prompt injection heuristics --------------------------------------------
# Deliberately simple substring/regex heuristics, not a full classifier - good
# enough to demonstrate the guardrail layer and catch unsophisticated attempts.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|the)? ?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (all|any|the)? ?(previous|prior|above) instructions", re.I),
    re.compile(r"you are now[ ,]", re.I),
    re.compile(r"reveal your (system )?prompt", re.I),
    re.compile(r"print your (system )?instructions", re.I),
    re.compile(r"act as (if you|though you)? ?(are|were) (not|no longer)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"\bDAN\b"),
]

# --- PII patterns for masking in logs/traces only ---------------------------
_PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"),
    "card_number": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "pan_india": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "aadhaar_india": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
}


@dataclass
class GuardrailResult:
    blocked: bool
    event_type: str
    detail: str | None = None


def check_prompt_injection(text: str) -> GuardrailResult:
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return GuardrailResult(
                blocked=True,
                event_type="prompt_injection",
                detail=f"matched pattern: {match.group(0)!r}",
            )
    return GuardrailResult(blocked=False, event_type="prompt_injection")


def mask_pii(text: str) -> str:
    """Replace PII-shaped substrings with a `[REDACTED:<kind>]` marker.

    Intended for anything sent to logs/metrics/trace metadata - never applied
    to the response actually returned to the authenticated account holder.
    """
    masked = text
    for kind, pattern in _PII_PATTERNS.items():
        masked = pattern.sub(f"[REDACTED:{kind}]", masked)
    return masked


def detect_pii_kinds(text: str) -> list[str]:
    return [kind for kind, pattern in _PII_PATTERNS.items() if pattern.search(text)]


class GuardrailBlocked(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def enforce_input(text: str, *, tenant_id: str, agent: str | None = None) -> None:
    """Run input guardrails; raise GuardrailBlocked if the request should be
    rejected. Also logs guardrail events (blocks and PII sightings) for the
    /metrics/guardrails dashboard. No-ops entirely if GUARDRAILS_ENABLED=false.
    """
    if not GUARDRAILS_ENABLED:
        return

    injection = check_prompt_injection(text)
    if injection.blocked:
        insert_guardrail_event(
            run_id=None, tenant_id=tenant_id, agent=agent, direction="input",
            event_type=injection.event_type, blocked=True, detail=injection.detail,
        )
        raise GuardrailBlocked(f"Blocked potential prompt injection ({injection.detail}).")

    pii_kinds = detect_pii_kinds(text)
    if pii_kinds:
        insert_guardrail_event(
            run_id=None, tenant_id=tenant_id, agent=agent, direction="input",
            event_type="pii_detected", blocked=False, detail=",".join(pii_kinds),
        )
