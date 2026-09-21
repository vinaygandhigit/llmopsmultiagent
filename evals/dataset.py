"""Golden evaluation dataset for the multiagent bank assistant (Evals gap #2).

Every case's `expected_keywords` are pulled directly from the bank.db seed
data (see app/database.py) - real ground truth, not invented numbers - so the
deterministic `context_precision` evaluator in evals/evaluators.py can check
the agent's answer is actually grounded on the correct record. `reference` is
a human-quality answer used as additional grounding for the LLM-as-judge
evaluators (faithfulness, answer_relevance).
"""
from __future__ import annotations

GOLDEN_DATASET: list[dict] = [
    # --- account_agent ---
    {
        "id": "account-001",
        "agent": "account_agent",
        "question": "What is the balance for account ACC10001?",
        "reference": "Account ACC10001 belongs to John Smith. Balance: 15230.50 USD. Status: ACTIVE.",
        "expected_keywords": ["15,230.50", "John Smith", "ACTIVE"],
    },
    {
        "id": "account-002",
        "agent": "account_agent",
        "question": "Can you check the account details for ACC10003?",
        "reference": "Account ACC10003 belongs to Michael Brown. Type: SAVINGS. Balance: 32100.00 USD. Branch: Downtown.",
        "expected_keywords": ["32,100", "Michael Brown", "SAVINGS"],
    },
    {
        "id": "account-003",
        "agent": "account_agent",
        "question": "What's the balance on account ACC99999?",
        "reference": "No account found with account number 'ACC99999'.",
        "expected_keywords": ["no account found", "acc99999"],
    },
    # --- transaction_agent ---
    {
        "id": "transaction-001",
        "agent": "transaction_agent",
        "question": "Show me recent transactions for ACC10001.",
        "reference": "Salary credit of 2500.00 on 2026-08-01 and a utility payment debit of 120.50 on 2026-08-05.",
        "expected_keywords": ["2,500", "salary", "120.50", "utility"],
    },
    {
        "id": "transaction-002",
        "agent": "transaction_agent",
        "question": "What was the opening and closing balance on the last statement for ACC10001?",
        "reference": "Statement for 2026-07-01 to 2026-07-31: opening balance 12851.00, closing balance 15230.50.",
        "expected_keywords": ["12,851", "15,230.50"],
    },
    # --- service_agent ---
    {
        "id": "service-001",
        "agent": "service_agent",
        "question": "What's the cheque book request status for ACC10001?",
        "reference": "Cheque book request status: DELIVERED, 50 leaves, requested 2026-07-25, delivered 2026-07-30.",
        "expected_keywords": ["delivered", "50"],
    },
    {
        "id": "service-002",
        "agent": "service_agent",
        "question": "Is the KYC verified for account ACC10003?",
        "reference": "KYC status: REJECTED. Remarks: Document verification failed.",
        "expected_keywords": ["rejected", "document verification failed"],
    },
    {
        "id": "service-003",
        "agent": "service_agent",
        "question": "What is the address update status for ACC10002?",
        "reference": "Address update status: PENDING. Requested address: 22 Park Avenue, Uptown.",
        "expected_keywords": ["pending", "22 Park Avenue"],
    },
    # --- bank_supervisor (multi-topic routing) ---
    {
        "id": "supervisor-001",
        "agent": "bank_supervisor",
        "question": "Show my transactions and cheque book status for ACC10001.",
        "reference": "Transactions: salary credit 2500.00, utility debit 120.50. Cheque book: DELIVERED, 50 leaves.",
        "expected_keywords": ["2,500", "delivered"],
    },
    {
        "id": "supervisor-002",
        "agent": "bank_supervisor",
        "question": "What is my account balance for ACC10002?",
        "reference": "Account ACC10002 belongs to Emma Johnson. Balance: 8420.75 USD. Type: CURRENT.",
        "expected_keywords": ["8,420.75", "Emma Johnson"],
    },
]


def cases_for_agent(agent_key: str) -> list[dict]:
    return [case for case in GOLDEN_DATASET if case["agent"] == agent_key]