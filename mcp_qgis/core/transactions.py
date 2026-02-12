from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..errors import ConflictError, NotFoundError


@dataclass
class Transaction:
    transaction_id: str
    plan_id: str
    session_id: str
    status: str = "open"
    events: list[dict[str, Any]] = field(default_factory=list)


class TransactionManager:
    def __init__(self) -> None:
        self._tx: dict[str, Transaction] = {}

    def begin(self, plan_id: str, session_id: str) -> Transaction:
        tx = Transaction(transaction_id=str(uuid4()), plan_id=plan_id, session_id=session_id)
        self._tx[tx.transaction_id] = tx
        self._record(tx, "tx.begin", "open")
        return tx

    def step(self, transaction_id: str, step_id: str, status: str, details: dict[str, Any] | None = None) -> None:
        tx = self._get(transaction_id)
        self._record(tx, f"tx.step.{status}", status, step_id=step_id, details=details or {})
        if status == "failed":
            tx.status = "failed"

    def commit(self, transaction_id: str) -> None:
        tx = self._get(transaction_id)
        if tx.status == "failed":
            raise ConflictError("Cannot commit failed transaction", {"transaction_id": transaction_id})
        tx.status = "committed"
        self._record(tx, "tx.commit", "committed")

    def rollback(self, transaction_id: str) -> None:
        tx = self._get(transaction_id)
        tx.status = "rolled_back"
        self._record(tx, "tx.rollback", "rolled_back")

    def mark_recovery_pending(self, transaction_id: str) -> None:
        tx = self._get(transaction_id)
        tx.status = "recovery_pending"
        self._record(tx, "tx.recovery_pending", "recovery_pending")

    def recover_open_transactions(self) -> list[str]:
        pending = []
        for tx in self._tx.values():
            if tx.status == "open":
                tx.status = "recovery_pending"
                self._record(tx, "tx.recovery_pending", "recovery_pending")
                pending.append(tx.transaction_id)
        return pending

    def get_log(self, transaction_id: str) -> list[dict[str, Any]]:
        return list(self._get(transaction_id).events)

    def _get(self, transaction_id: str) -> Transaction:
        tx = self._tx.get(transaction_id)
        if not tx:
            raise NotFoundError("Transaction not found", {"transaction_id": transaction_id})
        return tx

    @staticmethod
    def _record(tx: Transaction, event: str, status: str, **extra: Any) -> None:
        tx.events.append(
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "transaction_id": tx.transaction_id,
                "plan_id": tx.plan_id,
                "event": event,
                "status": status,
                **extra,
            }
        )
