"""Structured logging setup via structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(*, json_output: bool = False, level: str = "INFO") -> None:
    """Configure structlog processors and stdlib log level."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, level.upper()), stream=sys.stderr)
