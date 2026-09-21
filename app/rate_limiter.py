"""Cost controls: per-tenant request rate limiting and daily token budgets.

This is an in-memory implementation (a sliding window per tenant) - good
enough for a single-process demo. A multi-instance production deployment
would back this with Redis or similar shared state instead of a
process-local dict.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.config import DAILY_TOKEN_BUDGET_PER_TENANT, RATE_LIMIT_PER_MINUTE
from app.database import sum_tokens_for_tenant_today

_lock = threading.Lock()
_request_timestamps: dict[str, deque] = defaultdict(deque)

_WINDOW_SECONDS = 60.0


class RateLimitExceeded(Exception):
    def __init__(self, tenant_id: str, limit: int):
        super().__init__(f"Tenant '{tenant_id}' exceeded {limit} requests/minute.")
        self.tenant_id = tenant_id
        self.limit = limit


class TokenBudgetExceeded(Exception):
    def __init__(self, tenant_id: str, used: int, budget: int):
        super().__init__(f"Tenant '{tenant_id}' has used {used}/{budget} tokens today.")
        self.tenant_id = tenant_id
        self.used = used
        self.budget = budget


@dataclass
class RateLimitStatus:
    tenant_id: str
    requests_in_window: int
    requests_limit: int
    tokens_used_today: int
    tokens_budget: int


def check_and_record_request(tenant_id: str) -> None:
    """Raise RateLimitExceeded if `tenant_id` is over the per-minute limit,
    otherwise record this request. Call once per inbound chat request,
    before the (expensive) LLM call.
    """
    now = time.monotonic()
    with _lock:
        window = _request_timestamps[tenant_id]
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceeded(tenant_id, RATE_LIMIT_PER_MINUTE)
        window.append(now)


def check_token_budget(tenant_id: str) -> None:
    """Raise TokenBudgetExceeded if `tenant_id` has already used its daily
    token budget. Checked before the LLM call using tokens already recorded
    from prior requests today (can't know this request's cost in advance).
    """
    used = sum_tokens_for_tenant_today(tenant_id)
    if used >= DAILY_TOKEN_BUDGET_PER_TENANT:
        raise TokenBudgetExceeded(tenant_id, used, DAILY_TOKEN_BUDGET_PER_TENANT)


def get_status(tenant_id: str) -> RateLimitStatus:
    now = time.monotonic()
    with _lock:
        window = _request_timestamps[tenant_id]
        cutoff = now - _WINDOW_SECONDS
        requests_in_window = sum(1 for t in window if t >= cutoff)
    return RateLimitStatus(
        tenant_id=tenant_id,
        requests_in_window=requests_in_window,
        requests_limit=RATE_LIMIT_PER_MINUTE,
        tokens_used_today=sum_tokens_for_tenant_today(tenant_id),
        tokens_budget=DAILY_TOKEN_BUDGET_PER_TENANT,
    )