"""
Модуль работы с базой данных SQLite.
Хранит результаты поиска, историю операций и кэш цен.
"""

import sqlite3
import json
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator, Optional

from config import DATABASE_PATH, CACHE_TTL_HOURS
from modules.logging.logger import get_logger

logger = get_logger(__name__)


# ─── DDL ─────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS search_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT    NOT NULL,
    finished_at TEXT,
    spec_file   TEXT    NOT NULL,
    region      TEXT    NOT NULL,
    total_items INTEGER DEFAULT 0,
    found_items INTEGER DEFAULT 0,
    status      TEXT    DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS spec_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES search_sessions(id),
    row_number INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    specs      TEXT,
    unit       TEXT,
    quantity   REAL,
    raw_data   TEXT
);

CREATE TABLE IF NOT EXISTS search_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_item_id  INTEGER NOT NULL REFERENCES spec_items(id),
    source        TEXT    NOT NULL,
    supplier_name TEXT,
    price         REAL,
    currency      TEXT    DEFAULT 'UZS',
    availability  INTEGER DEFAULT 0,
    address       TEXT,
    url           TEXT,
    match_score   REAL    DEFAULT 0.0,
    has_contacts  INTEGER DEFAULT 0,
    rank_score    REAL    DEFAULT 0.0,
    raw_data      TEXT,
    found_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS price_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT    NOT NULL UNIQUE,
    data        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES search_sessions(id),
    level      TEXT    NOT NULL,
    message    TEXT    NOT NULL,
    details    TEXT,
    logged_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_key     ON price_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON price_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_results_item  ON search_results(spec_item_id);
CREATE INDEX IF NOT EXISTS idx_items_session ON spec_items(session_id);
"""


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Контекстный менеджер подключения к SQLite."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Создаёт схему БД при первом запуске."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("База данных инициализирована: %s", DATABASE_PATH)


# ─── Сессии ───────────────────────────────────────────────────────────────────

def create_session(spec_file: str, region: str) -> int:
    """Создаёт новую сессию поиска, возвращает её ID."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO search_sessions (started_at, spec_file, region)
            VALUES (?, ?, ?)
            """,
            (datetime.now().isoformat(), spec_file, region),
        )
        return cur.lastrowid


def finish_session(session_id: int, total: int, found: int, status: str = "done") -> None:
    """Обновляет статус завершённой сессии."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE search_sessions
            SET finished_at=?, total_items=?, found_items=?, status=?
            WHERE id=?
            """,
            (datetime.now().isoformat(), total, found, status, session_id),
        )


# ─── Позиции спецификации ────────────────────────────────────────────────────

def save_spec_items(session_id: int, items: list[dict]) -> list[int]:
    """Сохраняет позиции спецификации, возвращает список ID."""
    ids: list[int] = []
    with get_connection() as conn:
        for item in items:
            cur = conn.execute(
                """
                INSERT INTO spec_items (session_id, row_number, name, specs, unit, quantity, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("row_number", 0),
                    item.get("name", ""),
                    item.get("specs", ""),
                    item.get("unit", ""),
                    item.get("quantity"),
                    json.dumps(item, ensure_ascii=False),
                ),
            )
            ids.append(cur.lastrowid)
    return ids


# ─── Результаты поиска ───────────────────────────────────────────────────────

def save_search_result(spec_item_id: int, result: dict) -> int:
    """Сохраняет одно найденное предложение от поставщика."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO search_results
              (spec_item_id, source, supplier_name, price, currency,
               availability, address, url, match_score, has_contacts,
               rank_score, raw_data, found_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                spec_item_id,
                result.get("source", ""),
                result.get("supplier_name", ""),
                result.get("price"),
                result.get("currency", "UZS"),
                int(result.get("availability", False)),
                result.get("address", ""),
                result.get("url", ""),
                result.get("match_score", 0.0),
                int(result.get("has_contacts", False)),
                result.get("rank_score", 0.0),
                json.dumps(result, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        return cur.lastrowid


def get_results_for_session(session_id: int) -> list[dict]:
    """Возвращает все результаты поиска для сессии."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT si.row_number, si.name, si.specs, si.unit, si.quantity,
                   sr.supplier_name, sr.price, sr.currency, sr.availability,
                   sr.address, sr.url, sr.match_score, sr.rank_score, sr.source
            FROM spec_items si
            JOIN search_results sr ON sr.spec_item_id = si.id
            WHERE si.session_id = ?
            ORDER BY si.row_number, sr.rank_score DESC
            """,
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Кэш ─────────────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[list[dict]]:
    """Возвращает данные из кэша или None если устарел/отсутствует."""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT data FROM price_cache WHERE cache_key=? AND expires_at>?",
            (key, now),
        ).fetchone()
    if row:
        return json.loads(row["data"])
    return None


def cache_set(key: str, data: list[dict]) -> None:
    """Сохраняет данные в кэш с TTL."""
    now = datetime.now()
    expires = (now + timedelta(hours=CACHE_TTL_HOURS)).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO price_cache (cache_key, data, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                data=excluded.data,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at
            """,
            (key, json.dumps(data, ensure_ascii=False), now.isoformat(), expires),
        )


def cache_cleanup() -> None:
    """Удаляет устаревшие записи кэша."""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM price_cache WHERE expires_at<?", (now,)
        ).rowcount
    if deleted:
        logger.debug("Кэш очищен: удалено %d устаревших записей", deleted)


# ─── Журнал операций ─────────────────────────────────────────────────────────

def log_operation(
    session_id: Optional[int],
    level: str,
    message: str,
    details: Optional[str] = None,
) -> None:
    """Записывает событие в журнал операций БД."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO operation_log (session_id, level, message, details, logged_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, level, message, details, datetime.now().isoformat()),
        )
