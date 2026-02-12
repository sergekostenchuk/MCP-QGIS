from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s session_id=%(session_id)s tx_id=%(transaction_id)s %(message)s",
    )


class RequestContextFilter(logging.Filter):
    """Inject default correlation ids when absent."""

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("request_id", "session_id", "transaction_id"):
            if not hasattr(record, attr):
                setattr(record, attr, "-")
        return True
