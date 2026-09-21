"""LangChain tools available to the account agent."""
from langchain_core.tools import tool

from app.database import (
    get_address_update,
    get_balance_by_account_number,
    get_cheque_book_update_status,
    get_kyc_update_status,
    get_statement_details,
    get_transaction_details,
)


def _account_number(value: str) -> str:
    return value.strip().upper()


@tool
def balance_enquiry(account_number: str) -> str:
    """Look up the current balance and details for a bank account given its account number.

    Args:
        account_number: The account number to look up, e.g. 'ACC10001'.
    """
    record = get_balance_by_account_number(_account_number(account_number))
    if record is None:
        return f"No account found with account number '{account_number}'."

    return (
        f"Account {record['account_number']} belongs to {record['customer_name']}. "
        f"Type: {record['account_type']}, Status: {record['status']}, "
        f"Balance: {record['balance']:.2f} {record['currency']}, Branch: {record['branch']}."
    )


@tool
def transaction_details(account_number: str) -> str:
    """Get recent credit and debit transactions for a bank account."""
    rows = get_transaction_details(_account_number(account_number))
    if not rows:
        return f"No transaction details found for account '{account_number}'."
    return "\n".join(
        f"{row['transaction_date']}: {row['transaction_type']} "
        f"{row['amount']:.2f} - {row['description']} "
        f"(balance after: {row['balance_after']:.2f})"
        for row in rows
    )


@tool
def statement_details(account_number: str) -> str:
    """Get available statement periods and balances for a bank account."""
    rows = get_statement_details(_account_number(account_number))
    if not rows:
        return f"No statement details found for account '{account_number}'."
    return "\n".join(
        f"{row['period_start']} to {row['period_end']}: "
        f"opening {row['opening_balance']:.2f}, closing {row['closing_balance']:.2f}"
        for row in rows
    )


@tool
def address_update(account_number: str) -> str:
    """Check the latest address update request for a bank account."""
    row = get_address_update(_account_number(account_number))
    if row is None:
        return f"No address update found for account '{account_number}'."
    return (
        f"Address update status: {row['status']}. "
        f"Current address: {row['current_address']}. "
        f"Requested address: {row['requested_address']}."
    )


@tool
def kyc_update_status(account_number: str) -> str:
    """Check the latest KYC verification status for a bank account."""
    row = get_kyc_update_status(_account_number(account_number))
    if row is None:
        return f"No KYC update found for account '{account_number}'."
    return f"KYC status: {row['kyc_status']}. Remarks: {row['remarks']}."


@tool
def cheque_book_update_status(account_number: str) -> str:
    """Check the latest cheque book request status for a bank account."""
    row = get_cheque_book_update_status(_account_number(account_number))
    if row is None:
        return f"No cheque book request found for account '{account_number}'."
    delivered = row['delivered_at'] or "not delivered"
    return (
        f"Cheque book request status: {row['request_status']}, "
        f"leaves: {row['leaves']}, requested: {row['requested_at']}, "
        f"delivered: {delivered}."
    )