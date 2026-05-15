"""
Скрапер для Prom.uz — крупнейшей торговой площадки Узбекистана.
"""

import urllib.parse
from typing import Optional

from modules.search.base_scraper import BaseScraper
from modules.utils.models import SupplierResult
from modules.utils.helpers import fuzzy_match_score
from config import MAX_RESULTS_PER_SOURCE


class PromUzScraper(BaseScraper):
    source_id = "prom_uz"
    source_name = "Prom.uz"
    base_url = "https://prom.uz"

    def search(self, query: str, region: str) -> list[SupplierResult]:
        url = self._build_search_url(query, region)
        self.logger.info("Поиск на Prom.uz: %s", query[:60])

        html = self._fetch_page(url)
        if not html:
            return []

        results = self._parse_results(html, query)
        self.logger.info("Prom.uz: найдено %d предложений", len(results))
        return results

    def _build_search_url(self, query: str, region: str) -> str:
        params = urllib.parse.urlencode({"search_term": query, "region": region})
        return f"{self.base_url}/search?{params}"

    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        soup = self._soup(html)
        results: list[SupplierResult] = []

        # Prom.uz использует различные классы — пробуем несколько вариантов
        product_cards = (
            soup.select(".x-gallery-tile")
            or soup.select("[data-qaid='product_gallery_item']")
            or soup.select(".js-productCard")
            or soup.select("article.x-gallery-tile")
        )

        if not product_cards:
            self.logger.debug("Prom.uz: карточки товаров не найдены (возможно, блокировка)")
            return []

        for card in product_cards[:MAX_RESULTS_PER_SOURCE]:
            result = self._parse_card(card, query)
            if result:
                results.append(result)

        return results

    def _parse_card(self, card, query: str) -> Optional[SupplierResult]:
        try:
            # Название товара
            name_el = (
                card.select_one("[data-qaid='product_name']")
                or card.select_one(".x-gallery-tile__title")
                or card.select_one("a.x-gallery-tile__name")
            )
            if not name_el:
                return None

            product_name = self._clean_text(name_el)
            if not product_name:
                return None

            # URL товара
            link_el = card.select_one("a[href]")
            url = self._make_absolute_url(link_el["href"]) if link_el else self.base_url

            # Цена
            price_el = (
                card.select_one("[data-qaid='product_price']")
                or card.select_one(".x-gallery-tile__price")
            )
            price = self._safe_price(self._clean_text(price_el))

            # Поставщик
            supplier_el = (
                card.select_one("[data-qaid='company_name']")
                or card.select_one(".x-gallery-tile__company")
            )
            supplier_name = self._clean_text(supplier_el) or "Поставщик на Prom.uz"

            # Наличие
            availability = self._detect_availability(card)

            # Контакты
            has_contacts = bool(card.select_one("[data-qaid='company_phone']"))

            # Оценка совпадения
            match_score = fuzzy_match_score(query, product_name) / 100.0

            return SupplierResult(
                source=self.source_id,
                supplier_name=supplier_name,
                url=url,
                price=price,
                currency="UZS",
                availability=availability,
                match_score=match_score,
                has_contacts=has_contacts,
                specs_found=product_name,
            )

        except Exception as e:
            self.logger.debug("Ошибка парсинга карточки Prom.uz: %s", e)
            return None

    def _detect_availability(self, card) -> bool:
        """Определяет наличие товара по тексту на карточке."""
        availability_el = card.select_one(
            "[data-qaid='product_presence'], .x-gallery-tile__presence"
        )
        if not availability_el:
            return True  # По умолчанию считаем в наличии

        text = self._clean_text(availability_el).lower()
        negative_keywords = ["нет в наличии", "под заказ", "ожидается", "нет на складе"]
        return not any(kw in text for kw in negative_keywords)
