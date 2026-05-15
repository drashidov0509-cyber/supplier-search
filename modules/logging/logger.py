"""
Модуль логирования.
Настраивает единую систему логов для всего приложения.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import (
    LOGS_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)


def setup_logging() -> None:
    """Инициализирует систему логирования: файлы + консоль."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── Консольный обработчик ────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── Общий лог (INFO+) ────────────────────────────────────────────────────
    _add_file_handler(
        root_logger,
        LOGS_DIR / "app.log",
        logging.INFO,
        formatter,
    )

    # ── Лог ошибок (ERROR+) ──────────────────────────────────────────────────
    _add_file_handler(
        root_logger,
        LOGS_DIR / "errors.log",
        logging.ERROR,
        formatter,
    )

    # ── Лог поиска ───────────────────────────────────────────────────────────
    search_logger = logging.getLogger("search")
    _add_file_handler(
        search_logger,
        LOGS_DIR / "search.log",
        logging.DEBUG,
        formatter,
    )


def _add_file_handler(
    logger: logging.Logger,
    path: Path,
    level: int,
    formatter: logging.Formatter,
) -> None:
    handler = RotatingFileHandler(
        path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер."""
    return logging.getLogger(name)
