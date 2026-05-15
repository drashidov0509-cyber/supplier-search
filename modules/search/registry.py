"""
Реестр источников поиска.
Добавление нового источника — только здесь, без изменения основной логики.
"""

from typing import Type

from modules.search.base_scraper import BaseScraper
from modules.search.prom_uz import PromUzScraper
from modules.search.olx_uz import OlxUzScraper
from modules.search.other_scrapers import GlotrUzScraper, StroykаUzScraper
from config import ENABLED_SOURCES
from modules.logging.logger import get_logger

logger = get_logger(__name__)

# ─── Регистрация источников ───────────────────────────────────────────────────
# Чтобы добавить новый источник:
#   1. Создать класс-наследник BaseScraper
#   2. Добавить его в этот словарь
#   3. Добавить его source_id в ENABLED_SOURCES в config.py

_SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "prom_uz": PromUzScraper,
    "olx_uz": OlxUzScraper,
    "glotr_uz": GlotrUzScraper,
    "stroyka_uz": StroykаUzScraper,
}


def get_active_scrapers() -> list[BaseScraper]:
    """
    Возвращает список инстансов активных scrapers.
    Активные — те, чьи ID перечислены в ENABLED_SOURCES.
    """
    scrapers: list[BaseScraper] = []

    for source_id in ENABLED_SOURCES:
        cls = _SCRAPER_REGISTRY.get(source_id)
        if cls is None:
            logger.warning("Источник '%s' зарегистрирован в ENABLED_SOURCES, но не найден в реестре", source_id)
            continue
        scrapers.append(cls())
        logger.debug("Подключён источник: %s", source_id)

    logger.info("Активных источников: %d", len(scrapers))
    return scrapers


def register_scraper(source_id: str, scraper_class: Type[BaseScraper]) -> None:
    """
    Динамически регистрирует новый источник.
    Может использоваться для плагинов.
    """
    _SCRAPER_REGISTRY[source_id] = scraper_class
    logger.info("Зарегистрирован новый источник: %s", source_id)


def list_available_sources() -> list[str]:
    """Возвращает список всех зарегистрированных source_id."""
    return list(_SCRAPER_REGISTRY.keys())
