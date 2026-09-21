"""SQLite database setup and helpers for the multiagent bank demo."""
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "bank.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- LLMOps tables -----------------------------------------------------------
# These are additive to the pre-existing banking schema and back the
# observability/feedback/guardrail features: token usage & cost per request,
# end-user feedback tied to LangSmith run ids, LLM-as-judge quality scores
# (for hallucination/drift monitoring), and guardrail block/flag events.

_LLMOPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'anonymous',
    agent TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    slo_breached INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'anonymous',
    agent TEXT,
    score REAL NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    agent TEXT NOT NULL,
    metric TEXT NOT NULL DEFAULT 'faithfulness',
    score REAL NOT NULL,
    rationale TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guardrail_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'anonymous',
    agent TEXT,
    direction TEXT NOT NULL,
    event_type TEXT NOT NULL,
    blocked INTEGER NOT NULL DEFAULT 0,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


def init_llmops_tables() -> None:
    """Create the LLMOps observability/feedback/guardrail tables if missing.

    Safe to call on every app startup - CREATE TABLE IF NOT EXISTS is
    idempotent, so this never touches the pre-existing banking tables.
    """
    conn = get_connection()
    try:
        conn.executescript(_LLMOPS_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def get_balance_by_account_number(account_number: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT account_number, customer_name, account_type, balance, currency, branch, status "
            "FROM accounts WHERE account_number = ?",
            (account_number,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_transaction_details(account_number: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT transaction_id, transaction_type, amount, description, "
            "transaction_date, balance_after FROM transactions "
            "WHERE account_number = ? ORDER BY transaction_date DESC",
            (account_number,),
        ).fetchall()
    finally:
        conn.close()


def get_statement_details(account_number: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT statement_id, period_start, period_end, opening_balance, "
            "closing_balance, generated_at FROM statements "
            "WHERE account_number = ? ORDER BY period_end DESC",
            (account_number,),
        ).fetchall()
    finally:
        conn.close()


def get_address_update(account_number: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT address_id, current_address, requested_address, status, "
            "requested_at FROM address_updates WHERE account_number = ? "
            "ORDER BY requested_at DESC LIMIT 1",
            (account_number,),
        ).fetchone()
    finally:
        conn.close()


def get_kyc_update_status(account_number: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT kyc_id, kyc_status, remarks, updated_at FROM kyc_updates "
            "WHERE account_number = ? ORDER BY updated_at DESC LIMIT 1",
            (account_number,),
        ).fetchone()
    finally:
        conn.close()


def insert_usage_metric(
    *,
    run_id: str | None,
    tenant_id: str,
    agent: str,
    model: str,
    prompt_version: str | None,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost_usd: float,
    latency_ms: float,
    slo_breached: bool,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO usage_metrics (run_id, tenant_id, agent, model, prompt_version, "
            "input_tokens, output_tokens, total_tokens, cost_usd, latency_ms, slo_breached, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, tenant_id, agent, model, prompt_version,
                input_tokens, output_tokens, total_tokens, cost_usd, latency_ms,
                1 if slo_breached else 0, _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def sum_tokens_for_tenant_today(tenant_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) AS total FROM usage_metrics "
            "WHERE tenant_id = ? AND date(created_at) = date('now')",
            (tenant_id,),
        ).fetchone()
        return int(row["total"])
    finally:
        conn.close()


def get_usage_summary() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT agent, model, COUNT(*) AS requests, SUM(input_tokens) AS input_tokens, "
            "SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens, "
            "SUM(cost_usd) AS cost_usd, AVG(latency_ms) AS avg_latency_ms, "
            "SUM(slo_breached) AS slo_breaches FROM usage_metrics GROUP BY agent, model"
        ).fetchall()
    finally:
        conn.close()


def insert_feedback(*, run_id: str, tenant_id: str, agent: str | None, score: float, comment: str | None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO feedback (run_id, tenant_id, agent, score, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, tenant_id, agent, score, comment, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_feedback_summary() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT agent, COUNT(*) AS responses, AVG(score) AS avg_score, "
            "SUM(CASE WHEN score < 0 THEN 1 ELSE 0 END) AS negative_count "
            "FROM feedback GROUP BY agent"
        ).fetchall()
    finally:
        conn.close()


def get_negative_feedback_runs(threshold: float = 0) -> list[sqlite3.Row]:
    """Runs with feedback below `threshold` - candidates for the regression eval dataset."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT run_id, tenant_id, agent, score, comment, created_at FROM feedback "
            "WHERE score < ? ORDER BY created_at DESC",
            (threshold,),
        ).fetchall()
    finally:
        conn.close()


def insert_quality_score(
    *, run_id: str | None, agent: str, metric: str, score: float, rationale: str | None
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO quality_scores (run_id, agent, metric, score, rationale, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, agent, metric, score, rationale, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_quality_drift(bucket: str = "day") -> list[sqlite3.Row]:
    """Rolling average quality score per time bucket, per agent - surfaces drift over time."""
    strftime_fmt = "%Y-%m-%d" if bucket == "day" else "%Y-%m-%d %H:00"
    conn = get_connection()
    try:
        return conn.execute(
            f"SELECT agent, metric, strftime('{strftime_fmt}', created_at) AS bucket, "
            "AVG(score) AS avg_score, MIN(score) AS min_score, COUNT(*) AS samples "
            "FROM quality_scores GROUP BY agent, metric, bucket ORDER BY bucket ASC"
        ).fetchall()
    finally:
        conn.close()


def insert_guardrail_event(
    *,
    run_id: str | None,
    tenant_id: str,
    agent: str | None,
    direction: str,
    event_type: str,
    blocked: bool,
    detail: str | None,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO guardrail_events (run_id, tenant_id, agent, direction, event_type, "
            "blocked, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, tenant_id, agent, direction, event_type, 1 if blocked else 0, detail, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_guardrail_summary() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT event_type, direction, COUNT(*) AS occurrences, "
            "SUM(blocked) AS blocked_count FROM guardrail_events "
            "GROUP BY event_type, direction"
        ).fetchall()
    finally:
        conn.close()


def get_cheque_book_update_status(account_number: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT request_id, leaves, request_status, requested_at, "
            "delivered_at FROM cheque_book_requests WHERE account_number = ? "
            "ORDER BY requested_at DESC LIMIT 1",
            (account_number,),
        ).fetchone()
    finally:
        conn.close()