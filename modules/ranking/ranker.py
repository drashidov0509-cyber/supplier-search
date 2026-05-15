"""
Модуль ранжирования поставщиков.
Вычисляет итоговый score для каждого предложения по нескольким критериям.
"""

from modules.utils.models import SupplierResult, SearchTask
from config import RANKING_WEIGHTS
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class Ranker:
    """
    Ранжирует список предложений по комбинированному score.

    Критерии (веса из config.RANKING_WEIGHTS):
      1. price        — нормализованная обратная цена (дешевле = лучше)
      2. availability — наличие товара
      3. match_score  — схожесть с поисковым запросом
      4. contacts     — наличие контактной информации
    """

    def rank(self, results: list[SupplierResult]) -> list[SupplierResult]:
        """
        Вычисляет rank_score для каждого результата и сортирует по убыванию.
        """
        if not results:
            return []

        # Нормализуем цены в диапазон [0, 1]
        price_scores = self._normalize_prices([r.price for r in results])

        for result, price_score in zip(results, price_scores):
            result.rank_score = self._compute_score(result, price_score)

        ranked = sorted(results, key=lambda r: r.rank_score, reverse=True)
        logger.debug("Отранжировано %d предложений", len(ranked))
        return ranked

    def rank_tasks(self, tasks: list[SearchTask]) -> list[SearchTask]:
        """Ранжирует результаты во всех задачах."""
        for task in tasks:
            task.results = self.rank(task.results)
        return tasks

    # ── Приватные методы ──────────────────────────────────────────────────────

    def _compute_score(self, result: SupplierResult, price_score: float) -> float:
        """Вычисляет взвешенный итоговый score."""
        w = RANKING_WEIGHTS

        availability_score = 1.0 if result.availability else 0.0
        contacts_score = 1.0 if result.has_contacts else 0.0

        score = (
            w["price"] * price_score
            + w["availability"] * availability_score
            + w["match_score"] * result.match_score
            + w["contacts"] * contacts_score
        )

        return round(score, 4)

    @staticmethod
    def _normalize_prices(prices: list[float | None]) -> list[float]:
        """
        Нормализует цены: самая низкая получает 1.0, самая высокая — 0.0.
        Результаты без цены получают нейтральный score 0.3.
        """
        valid_prices = [p for p in prices if p is not None and p > 0]

        if not valid_prices:
            return [0.3] * len(prices)

        min_price = min(valid_prices)
        max_price = max(valid_prices)
        price_range = max_price - min_price

        normalized: list[float] = []
        for price in prices:
            if price is None or price <= 0:
                normalized.append(0.3)  # Нет цены — нейтральный score
            elif price_range == 0:
                normalized.append(1.0)  # Все цены одинаковые
            else:
                # Инвертируем: чем ниже цена, тем выше score
                score = 1.0 - (price - min_price) / price_range
                normalized.append(round(score, 4))

        return normalized
