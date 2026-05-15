"""
Скрапер для OLX.uz — доска объявлений с товарами от поставщиков.
"""

import urllib.parse
from typing import Optional

from modules.search.base_scraper import BaseScraper
from modules.utils.models import SupplierResult
from modules.utils.helpers import fuzzy_match_score
from config import MAX_RESULTS_PER_SOURCE


class OlxUzScraper(BaseScraper):
    source_id = "olx_uz"
    source_name = "OLX.uz"
    base_url = "https://www.olx.uz"

    def search(self, query: str, region: str) -> list[SupplierResult]:
        url = self._build_search_url(query, region)
        self.logger.info("Поиск на OLX.uz: %s", query[:60])

        html = self._fetch_page(url)
        if not html:
            return []

        results = self._parse_results(html, query)
        self.logger.info("OLX.uz: найдено %d предложений", len(results))
        return results

    def _build_search_url(self, query: str, region: str) -> str:
        # OLX поиск: /items/q-{query}/
        q_slug = urllib.parse.quote_plus(query)
        return f"{self.base_url}/items/q-{q_slug}/"

    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        soup = self._soup(html)
        results: list[SupplierResult] = []

        # OLX использует data-cy атрибуты
        cards = (
            soup.select("[data-cy='l-card']")
            or soup.select(".offer-wrapper")
            or soup.select("li.offer")
        )

        if not cards:
            self.logger.debug("OLX.uz: карточки не найдены")
            return []

        for card in cards[:MAX_RESULTS_PER_SOURCE]:
            result = self._parse_card(card, query)
            if result:
                results.append(result)

        return results

    def _parse_card(self, card, query: str) -> Optional[SupplierResult]:
        try:
            # Название
            name_el = (
                card.select_one("[data-cy='ad-card-title']")
                or card.select_one("h6")
                or card.select_one(".offer-title")
            )
            if not name_el:
                return None

            product_name = self._clean_text(name_el)
            if not product_name:
                return None

            # URL
            link_el = card.select_one("a[href]")
            url = self._make_absolute_url(link_el["href"]) if link_el else self.base_url

            # Цена
            price_el = (
                card.select_one("[data-testid='ad-price']")
                or card.select_one(".price strong")
                or card.select_one("p[data-testid='ad-price']")
            )
            price = self._safe_price(self._clean_text(price_el))

            # Местоположение (используем как адрес)
            location_el = (
                card.select_one("[data-testid='location-date']")
                or card.select_one(".location-name")
            )
            address = self._clean_text(location_el).split("-")[0].strip() if location_el else ""

            match_score = fuzzy_match_score(query, product_name) / 100.0

            return SupplierResult(
                source=self.source_id,
                supplier_name="Продавец на OLX.uz",
                url=url,
                price=price,
                currency="UZS",
                availability=True,  # OLX — активные объявления
                address=address,
                match_score=match_score,
                specs_found=product_name,
            )

        except Exception as e:
            self.logger.debug("Ошибка парсинга карточки OLX.uz: %s", e)
            return None
