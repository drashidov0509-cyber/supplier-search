"""
Скраперы для Glotr.uz и Stroyka.uz.
"""

import urllib.parse
from typing import Optional

from modules.search.base_scraper import BaseScraper
from modules.utils.models import SupplierResult
from modules.utils.helpers import fuzzy_match_score
from config import MAX_RESULTS_PER_SOURCE


# ─── Glotr.uz ────────────────────────────────────────────────────────────────

class GlotrUzScraper(BaseScraper):
    source_id = "glotr_uz"
    source_name = "Glotr.uz"
    base_url = "https://glotr.uz"

    def search(self, query: str, region: str) -> list[SupplierResult]:
        url = self._build_search_url(query, region)
        self.logger.info("Поиск на Glotr.uz: %s", query[:60])

        html = self._fetch_page(url)
        if not html:
            return []

        results = self._parse_results(html, query)
        self.logger.info("Glotr.uz: найдено %d предложений", len(results))
        return results

    def _build_search_url(self, query: str, region: str) -> str:
        params = urllib.parse.urlencode({"q": query})
        return f"{self.base_url}/search?{params}"

    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        soup = self._soup(html)
        results: list[SupplierResult] = []

        cards = (
            soup.select(".product-card")
            or soup.select(".item-card")
            or soup.select(".catalog-item")
        )

        if not cards:
            self.logger.debug("Glotr.uz: карточки не найдены")
            return []

        for card in cards[:MAX_RESULTS_PER_SOURCE]:
            result = self._parse_card(card, query)
            if result:
                results.append(result)

        return results

    def _parse_card(self, card, query: str) -> Optional[SupplierResult]:
        try:
            name_el = card.select_one(".product-name, .item-title, h3, h2")
            if not name_el:
                return None

            product_name = self._clean_text(name_el)
            if not product_name:
                return None

            link_el = card.select_one("a[href]")
            url = self._make_absolute_url(link_el["href"]) if link_el else self.base_url

            price_el = card.select_one(".price, .product-price, .cost")
            price = self._safe_price(self._clean_text(price_el))

            supplier_el = card.select_one(".supplier, .company, .seller")
            supplier_name = self._clean_text(supplier_el) or "Поставщик на Glotr.uz"

            match_score = fuzzy_match_score(query, product_name) / 100.0

            return SupplierResult(
                source=self.source_id,
                supplier_name=supplier_name,
                url=url,
                price=price,
                currency="UZS",
                availability=True,
                match_score=match_score,
                specs_found=product_name,
            )
        except Exception as e:
            self.logger.debug("Ошибка парсинга Glotr.uz: %s", e)
            return None


# ─── Stroyka.uz ──────────────────────────────────────────────────────────────

class StroykаUzScraper(BaseScraper):
    source_id = "stroyka_uz"
    source_name = "Stroyka.uz"
    base_url = "https://stroyka.uz"

    def search(self, query: str, region: str) -> list[SupplierResult]:
        url = self._build_search_url(query, region)
        self.logger.info("Поиск на Stroyka.uz: %s", query[:60])

        html = self._fetch_page(url)
        if not html:
            return []

        results = self._parse_results(html, query)
        self.logger.info("Stroyka.uz: найдено %d предложений", len(results))
        return results

    def _build_search_url(self, query: str, region: str) -> str:
        params = urllib.parse.urlencode({"query": query})
        return f"{self.base_url}/search?{params}"

    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        soup = self._soup(html)
        results: list[SupplierResult] = []

        cards = (
            soup.select(".product-item")
            or soup.select(".goods-item")
            or soup.select(".search-result-item")
        )

        if not cards:
            self.logger.debug("Stroyka.uz: карточки не найдены")
            return []

        for card in cards[:MAX_RESULTS_PER_SOURCE]:
            result = self._parse_card(card, query)
            if result:
                results.append(result)

        return results

    def _parse_card(self, card, query: str) -> Optional[SupplierResult]:
        try:
            name_el = card.select_one(".product-title, .name, h3, h4")
            if not name_el:
                return None

            product_name = self._clean_text(name_el)
            if not product_name:
                return None

            link_el = card.select_one("a[href]")
            url = self._make_absolute_url(link_el["href"]) if link_el else self.base_url

            price_el = card.select_one(".price, .cost")
            price = self._safe_price(self._clean_text(price_el))

            # Наличие
            availability_el = card.select_one(".availability, .stock")
            availability = True
            if availability_el:
                avail_text = self._clean_text(availability_el).lower()
                availability = "в наличии" in avail_text or "есть" in avail_text

            # Адрес поставщика
            address_el = card.select_one(".address, .location")
            address = self._clean_text(address_el)

            match_score = fuzzy_match_score(query, product_name) / 100.0

            return SupplierResult(
                source=self.source_id,
                supplier_name="Поставщик на Stroyka.uz",
                url=url,
                price=price,
                currency="UZS",
                availability=availability,
                address=address,
                match_score=match_score,
                specs_found=product_name,
            )
        except Exception as e:
            self.logger.debug("Ошибка парсинга Stroyka.uz: %s", e)
            return None
