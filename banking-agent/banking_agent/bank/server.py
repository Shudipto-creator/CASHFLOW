"""The mock bank as an MCP server, using bank2ai's standardized tool surface.

Run it (okgate does this for you as its `bank` upstream):

    python -m banking_agent.bank.server

The tool **names, input schemas and response models all come from bank2ai**.
This module supplies only handlers. Adding a business scenario means adding a
handler here, never renaming or reshaping a tool — that is the whole point of
using the adapter: the same agent code runs against any conformant bank.

Handlers that a scenario owner does not need can simply be omitted from the
`register_tools(...)` call, and the tool disappears from the surface.

Handler contract (from bank2ai.tools.register_tools):
  * keyword-only arguments matching the tool's input schema
  * return a bank2ai Pydantic response model
  * `raise` for transport-level failures; return a response with a `code` for
    business failures the agent should read and act on
"""

from __future__ import annotations

import asyncio
from typing import Optional

from bank2ai import register_tools
from fastmcp import FastMCP

from .ledger import Ledger


def build_server(ledger: Ledger | None = None) -> FastMCP:
    """Build the MCP server around `ledger` (a fresh one by default)."""
    bank = ledger or Ledger()

    async def get_accounts(
        *,
        only_withdrawal_accounts: bool = False,
        account_type: Optional[str] = None,
        status: Optional[str] = None,
        usage: Optional[str] = None,
    ):
        return await bank.get_accounts(
            only_withdrawal_accounts=only_withdrawal_accounts,
            account_type=account_type,
            status=status,
            usage=usage,
        )

    async def get_transactions(
        *,
        count: Optional[int] = None,
        order: str = "NewestFirst",
        verbosity: str = "minimal",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search_text: Optional[str] = None,
        category_ids: Optional[list[str]] = None,
        account_ids: Optional[list[str]] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        cursor: Optional[str] = None,
    ):
        return await bank.get_transactions(
            count=count,
            order=order,
            verbosity=verbosity,
            start_date=start_date,
            end_date=end_date,
            search_text=search_text,
            category_ids=category_ids,
            account_ids=account_ids,
            min_amount=min_amount,
            max_amount=max_amount,
            cursor=cursor,
        )

    async def get_transaction(*, transaction_id: str, account_id: Optional[str] = None):
        return await bank.get_transaction(transaction_id=transaction_id, account_id=account_id)

    async def get_categories():
        return await bank.get_categories()

    async def get_transactions_summary(
        *,
        direction: str,
        group_by: str = "category",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category_ids: Optional[list[str]] = None,
        account_ids: Optional[list[str]] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ):
        return await bank.get_transactions_summary(
            direction=direction,
            group_by=group_by,
            start_date=start_date,
            end_date=end_date,
            category_ids=category_ids,
            account_ids=account_ids,
            min_amount=min_amount,
            max_amount=max_amount,
        )

    async def get_recipients(*, name: str):
        return await bank.get_recipients(name=name)

    async def create_recipient(
        *,
        name: str,
        account_identifier: dict,
        national_id: Optional[dict] = None,
        nickname: Optional[str] = None,
        bic: Optional[str] = None,
        default_description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ):
        return await bank.create_recipient(
            name=name,
            account_identifier=account_identifier,
            national_id=national_id,
            nickname=nickname,
            bic=bic,
            default_description=default_description,
            idempotency_key=idempotency_key,
        )

    async def prepare_transfer(
        *,
        debtor_account_id: str,
        creditor: dict,
        amount: float,
        currency: str,
        rail: str,
        local_instrument: Optional[str] = None,
        requested_execution_date: Optional[str] = None,
        remittance_information: Optional[dict] = None,
        end_to_end_id: Optional[str] = None,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ):
        return await bank.prepare_transfer(
            debtor_account_id=debtor_account_id,
            creditor=creditor,
            amount=amount,
            currency=currency,
            rail=rail,
            local_instrument=local_instrument,
            requested_execution_date=requested_execution_date,
            remittance_information=remittance_information,
            end_to_end_id=end_to_end_id,
            description=description,
            idempotency_key=idempotency_key,
        )

    async def execute_transfer(
        *, transfer_intent_id: str, idempotency_key: Optional[str] = None
    ):
        return await bank.execute_transfer(
            transfer_intent_id=transfer_intent_id, idempotency_key=idempotency_key
        )

    app: FastMCP = FastMCP("banking-agent-mock-bank")
    register_tools(
        app,
        get_accounts=get_accounts,
        get_transactions=get_transactions,
        get_transaction=get_transaction,
        get_categories=get_categories,
        get_transactions_summary=get_transactions_summary,
        get_recipients=get_recipients,
        create_recipient=create_recipient,
        prepare_transfer=prepare_transfer,
        execute_transfer=execute_transfer,
    )
    return app


# Module-level instance so `python -m banking_agent.bank.server` works.
app = build_server()


def main() -> None:
    asyncio.run(app.run_async())


if __name__ == "__main__":
    main()
