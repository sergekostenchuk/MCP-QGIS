from __future__ import annotations

from mcp_qgis.core.transactions import TransactionManager


def test_transaction_commit_flow() -> None:
    txm = TransactionManager()
    tx = txm.begin("plan-1", "session-1")
    txm.step(tx.transaction_id, "s1", "running")
    txm.step(tx.transaction_id, "s1", "done")
    txm.commit(tx.transaction_id)
    log = txm.get_log(tx.transaction_id)
    assert any(e["event"] == "tx.commit" for e in log)


def test_recovery_marks_open_tx() -> None:
    txm = TransactionManager()
    tx = txm.begin("plan-2", "session-2")
    pending = txm.recover_open_transactions()
    assert tx.transaction_id in pending
