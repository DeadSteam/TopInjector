"""Project balance changes, shared by the panel API and the external API.

Balances are stored in kopeks (``Project.balance_credits``); callers pass rubles.
"""

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.project_service.domain.models import BalanceTransaction, Project


async def add_balance(session: AsyncSession, project: Project, amount_rub: float, description: str = "") -> BalanceTransaction:
    """Credit ``amount_rub`` to the project and record the transaction (commits)."""
    amount_kopeks = int(round(float(amount_rub) * 100))
    if amount_kopeks <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    project.balance_credits += amount_kopeks
    txn = BalanceTransaction(id=uuid4(), project_id=project.id, amount=amount_kopeks, description=description, type="add")
    session.add(txn)
    await session.commit()
    await session.refresh(project)
    return txn


async def set_balance(session: AsyncSession, project: Project, balance_rub: float, description: str = "Баланс установлен вручную") -> None:
    """Set the project balance to ``balance_rub``, recording the difference as a transaction (commits)."""
    new_kopeks = int(round(float(balance_rub) * 100))
    if new_kopeks < 0:
        raise HTTPException(status_code=400, detail="Balance can't be negative")

    diff = new_kopeks - project.balance_credits
    if diff != 0:
        session.add(BalanceTransaction(
            id=uuid4(), project_id=project.id, amount=diff, description=f"{description} (установка баланса)", type="set",
        ))
    project.balance_credits = new_kopeks
    await session.commit()
    await session.refresh(project)


def balance_payload(project: Project) -> dict:
    return {
        "project_id": str(project.id),
        "balance": project.balance_credits,
        "balance_rub": project.balance_credits / 100,
    }
