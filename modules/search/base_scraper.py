"""
Базовый класс скрапера.
Все источники наследуются от BaseScraper и реализуют метод search().
"""

from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from typing import Optional

from modules.utils.models import SupplierResult
from modules.utils.http_client import HttpClient
from modules.utils.helpers import parse_price
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class BaseScraper(ABC):
    """
    Абстрактный базовый класс для всех scrapers.

    Чтобы добавить новый источник:
    1. Создайте файл в modules/search/
    2. Наследуйтесь от BaseScraper
    3. Реализуйте абстрактные методы
    4. Зарегистрируйте в modules/search/registry.py
    """

    # Идентификатор источника (латиница, snake_case)
    source_id: str = ""

    # Человекочитаемое название
    source_name: str = ""

    # Базовый URL сайта
    base_url: str = ""

    def __init__(self) -> None:
        self.client = HttpClient()
        self.logger = get_logger(f"search.{self.source_id}")

    @abstractmethod
    def search(self, query: str, region: str) -> list[SupplierResult]:
        """
        Выполняет поиск по запросу.

        Args:
            query: поисковый запрос (нормализованный)
            region: регион поиска

        Returns:
            Список найденных предложений от поставщиков
        """
        ...

    @abstractmethod
    def _build_search_url(self, query: str, region: str) -> str:
        """Строит URL поиска для конкретного сайта."""
        ...

    @abstractmethod
    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        """Парсит HTML страницы результатов."""
        ...

    # ── Общие вспомогательные методы ─────────────────────────────────────────

    def _fetch_page(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Загружает страницу и возвращает HTML."""
        html = self.client.get(url, params=params)
        if not html:
            self.logger.warning("Пустой ответ от %s", url)
        return html

    @staticmethod
    def _soup(html: str) -> BeautifulSoup:
        """Создаёт BeautifulSoup объект."""
        return BeautifulSoup(html, "lxml")

    @staticmethod
    def _safe_price(text: Optional[str]) -> Optional[float]:
        """Безопасно парсит цену из текста."""
        if not text:
            return None
        return parse_price(text)

    @staticmethod
    def _clean_text(element) -> str:
        """Извлекает чистый текст из BS4-элемента."""
        if element is None:
            return ""
        return element.get_text(separator=" ", strip=True)

    def _make_absolute_url(self, path: str) -> str:
        """Превращает относительный путь в абсолютный URL."""
        if path.startswith("http"):
            return path
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
