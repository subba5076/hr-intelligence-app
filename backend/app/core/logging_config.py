"""
Structured (JSON) logging setup.

Plain text logs are hard to search once you have multiple pods running in
Kubernetes. Emitting one JSON object per log line means log aggregators
(Azure Monitor, Loki, ELK, etc.) can parse and filter on fields like
`level`, `request_id`, or `endpoint` without regex gymnastics.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra fields passed via logger.info(..., extra={...})
        for key in ("request_id", "endpoint", "duration_ms", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Quiet down noisy third-party loggers a bit.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
