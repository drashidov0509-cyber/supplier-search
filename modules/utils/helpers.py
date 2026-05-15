"""
Утилиты: нормализация текста, fuzzy matching, управление прокси и User-Agent.
"""

import re
import random
import hashlib
import unicodedata
from typing import Optional

from rapidfuzz import fuzz, process

from config import (
    USER_AGENTS,
    PROXY_LIST,
    FUZZY_MATCH_THRESHOLD,
)
from modules.logging.logger import get_logger

logger = get_logger(__name__)


# ─── Нормализация текста ─────────────────────────────────────────────────────

# Словарь сокращений единиц измерения
_UNIT_ALIASES: dict[str, str] = {
    "шт": "шт", "штук": "шт", "штука": "шт", "piece": "шт", "pcs": "шт",
    "м": "м", "метр": "м", "метров": "м", "meter": "м",
    "м2": "м²", "кв.м": "м²", "кв м": "м²", "m2": "м²",
    "м3": "м³", "куб.м": "м³", "m3": "м³",
    "кг": "кг", "килограмм": "кг", "kg": "кг",
    "т": "т", "тонн": "т", "тонна": "т", "ton": "т",
    "л": "л", "литр": "л", "liter": "л",
    "мл": "мл", "миллилитр": "мл",
    "упак": "уп", "упаковка": "уп", "уп.": "уп",
    "рул": "рул", "рулон": "рул",
    "комп": "компл", "комплект": "компл",
    "пог.м": "п.м", "погонный метр": "п.м",
}

# Символы, которые нужно нормализовать
_CHAR_MAP: dict[str, str] = {
    "х": "x",   # кириллическая х → латинская x (для размеров типа 3х2.5)
    "Х": "X",
    "×": "x",
    "·": ".",
    ",": ".",   # десятичная запятая → точка
}


def normalize_text(text: str) -> str:
    """
    Нормализует строку для сравнения:
    - приводит к нижнему регистру
    - убирает лишние пробелы
    - нормализует Unicode
    - заменяет спецсимволы
    """
    if not text:
        return ""
    # Unicode NFC-нормализация
    text = unicodedata.normalize("NFC", text)
    # Замена символов по карте
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    # Нижний регистр
    text = text.lower()
    # Убираем лишние пробелы и управляющие символы
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_unit(unit: str) -> str:
    """Нормализует единицу измерения по словарю псевдонимов."""
    if not unit:
        return ""
    cleaned = normalize_text(unit).rstrip(".")
    return _UNIT_ALIASES.get(cleaned, cleaned)


def build_search_query(name: str, specs: str = "", region: str = "") -> str:
    """
    Строит поисковый запрос из наименования и характеристик.
    Убирает стоп-слова и лишние символы.
    """
    parts = [name]
    if specs:
        parts.append(specs)

    query = " ".join(parts)

    # Убираем спецсимволы кроме дефиса, точки, слэша и цифровых разделителей
    query = re.sub(r"[^\w\s\-./×xх,]", " ", query, flags=re.UNICODE)
    query = re.sub(r"\s+", " ", query).strip()

    if region:
        query = f"{query} {region}"

    return query


def make_cache_key(query: str, source: str, region: str) -> str:
    """Создаёт уникальный ключ кэша для комбинации запрос+источник+регион."""
    raw = f"{normalize_text(query)}|{source}|{normalize_text(region)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ─── Fuzzy Matching ──────────────────────────────────────────────────────────

def fuzzy_match_score(query: str, candidate: str) -> float:
    """
    Возвращает оценку схожести двух строк (0-100).
    Использует комбинацию token_sort и partial_ratio для лучшего результата.
    """
    if not query or not candidate:
        return 0.0

    q = normalize_text(query)
    c = normalize_text(candidate)

    # token_sort_ratio хорош для перестановок слов
    score_sort = fuzz.token_sort_ratio(q, c)
    # partial_ratio хорош когда одна строка содержит другую
    score_partial = fuzz.partial_ratio(q, c)

    return max(score_sort, score_partial)


def is_similar(query: str, candidate: str, threshold: int = FUZZY_MATCH_THRESHOLD) -> bool:
    """Возвращает True если строки схожи выше порога."""
    return fuzzy_match_score(query, candidate) >= threshold


def find_best_match(
    query: str,
    candidates: list[str],
    threshold: int = FUZZY_MATCH_THRESHOLD,
) -> Optional[tuple[str, float]]:
    """
    Находит лучшее совпадение из списка кандидатов.
    Возвращает (лучший кандидат, score) или None.
    """
    if not candidates:
        return None

    q = normalize_text(query)
    normed = [normalize_text(c) for c in candidates]

    result = process.extractOne(
        q,
        normed,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )

    if result:
        matched_text, score, idx = result
        return candidates[idx], score

    return None


# ─── HTTP утилиты ─────────────────────────────────────────────────────────────

def get_random_user_agent() -> str:
    """Возвращает случайный User-Agent из списка."""
    return random.choice(USER_AGENTS)


def get_random_proxy() -> Optional[str]:
    """Возвращает случайный прокси или None если список пуст."""
    if not PROXY_LIST:
        return None
    return random.choice(PROXY_LIST)


def get_request_headers(extra: Optional[dict] = None) -> dict:
    """Формирует заголовки HTTP-запроса."""
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


# ─── Форматирование ───────────────────────────────────────────────────────────

def format_price(price: Optional[float], currency: str = "UZS") -> str:
    """Форматирует цену для отображения."""
    if price is None:
        return "—"
    return f"{price:,.0f} {currency}".replace(",", " ")


def parse_price(raw: str) -> Optional[float]:
    """
    Парсит цену из строки.
    Поддерживает форматы: '1 500 000', '1,500,000', '1500000.50'
    """
    if not raw:
        return None
    # Убираем всё кроме цифр, точки и запятой
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned:
        return None
    # Если запятая используется как десятичный разделитель
    if cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def availability_text(available: bool) -> str:
    """Возвращает текстовое описание наличия."""
    return "В наличии" if available else "Под заказ"
