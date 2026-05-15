"""
Поисковый движок.
Оркестрирует параллельный поиск по всем источникам,
кэширует результаты и выполняет дедупликацию.
"""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from modules.search.registry import get_active_scrapers
from modules.utils.models import SpecItem, SupplierResult, SearchTask
from modules.utils.helpers import build_search_query, make_cache_key, fuzzy_match_score
from modules.database.db import cache_get, cache_set
from config import MAX_WORKERS, MAX_RESULTS_PER_SOURCE, FUZZY_MATCH_THRESHOLD
from modules.logging.logger import get_logger

logger = get_logger("search")


class SearchEngine:
    """
    Выполняет поиск по всем активным источникам параллельно.
    Управляет кэшем, дедупликацией и обработкой ошибок.
    """

    def __init__(self) -> None:
        self.scrapers = get_active_scrapers()

    def search_item(self, spec_item: SpecItem, region: str) -> SearchTask:
        """
        Ищет одну позицию спецификации по всем источникам.
        Возвращает SearchTask с агрегированными результатами.
        """
        task = SearchTask(spec_item=spec_item, region=region)
        query = build_search_query(spec_item.name, spec_item.specs, region)

        logger.info("[%d] Поиск: %s", spec_item.row_number, query[:80])

        # Проверяем кэш
        all_results: list[SupplierResult] = []
        sources_to_search: list = []

        for scraper in self.scrapers:
            cache_key = make_cache_key(query, scraper.source_id, region)
            cached = cache_get(cache_key)

            if cached is not None:
                logger.debug("[%d] Кэш: %s (%d результатов)", spec_item.row_number, scraper.source_id, len(cached))
                all_results.extend(self._dicts_to_results(cached))
                task.from_cache = True
            else:
                sources_to_search.append((scraper, cache_key))

        # Параллельный поиск по источникам без кэша
        if sources_to_search:
            fresh_results = self._parallel_search(query, region, sources_to_search)
            all_results.extend(fresh_results)

        # Дедупликация
        unique_results = self._deduplicate(all_results)

        # Фильтрация по схожести с запросом
        query_clean = build_search_query(spec_item.name, spec_item.specs)
        filtered = [
            r for r in unique_results
            if r.match_score * 100 >= FUZZY_MATCH_THRESHOLD
        ]

        if not filtered and unique_results:
            # Если ничего не прошло порог — берём лучшие по совпадению
            filtered = sorted(unique_results, key=lambda r: r.match_score, reverse=True)[:5]

        task.results = filtered
        logger.info(
            "[%d] Итого: %d уникальных предложений (из %d)",
            spec_item.row_number, len(filtered), len(all_results),
        )
        return task

    def search_all(
        self,
        items: list[SpecItem],
        region: str,
        progress_callback=None,
    ) -> list[SearchTask]:
        """
        Ищет все позиции спецификации.
        progress_callback(current, total) вызывается после каждой позиции.
        """
        tasks: list[SearchTask] = []
        total = len(items)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_item = {
                executor.submit(self.search_item, item, region): item
                for item in items
            }

            completed = 0
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    task = future.result(timeout=60)
                    tasks.append(task)
                except TimeoutError:
                    logger.error("[%d] Таймаут поиска: %s", item.row_number, item.name)
                    tasks.append(SearchTask(spec_item=item, region=region, error="Таймаут"))
                except Exception as e:
                    logger.error("[%d] Ошибка поиска '%s': %s", item.row_number, item.name, e)
                    tasks.append(SearchTask(spec_item=item, region=region, error=str(e)))

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        # Сортируем по номеру строки для правильного порядка в отчёте
        tasks.sort(key=lambda t: t.spec_item.row_number)
        return tasks

    # ── Параллельный поиск по источникам ─────────────────────────────────────

    def _parallel_search(
        self,
        query: str,
        region: str,
        sources: list[tuple],
    ) -> list[SupplierResult]:
        """Запускает поиск по нескольким источникам параллельно."""
        results: list[SupplierResult] = []

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            future_to_source = {
                executor.submit(self._search_one_source, scraper, query, region, cache_key): scraper.source_id
                for scraper, cache_key in sources
            }

            for future in as_completed(future_to_source):
                source_id = future_to_source[future]
                try:
                    source_results = future.result(timeout=30)
                    results.extend(source_results)
                except Exception as e:
                    logger.error("Источник %s: ошибка: %s", source_id, e)

        return results

    def _search_one_source(
        self,
        scraper,
        query: str,
        region: str,
        cache_key: str,
    ) -> list[SupplierResult]:
        """Поиск по одному источнику с сохранением в кэш."""
        try:
            results = scraper.search(query, region)
            # Сохраняем в кэш даже пустой результат (чтобы не дёргать повторно)
            cache_set(cache_key, [r.to_dict() for r in results])
            return results
        except Exception as e:
            logger.error("Источник %s: неожиданная ошибка: %s", scraper.source_id, e)
            return []

    # ── Дедупликация ─────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate(results: list[SupplierResult]) -> list[SupplierResult]:
        """
        Удаляет дубликаты по URL и очень похожим названиям.
        """
        seen_urls: set[str] = set()
        unique: list[SupplierResult] = []

        for r in results:
            # Дедупликация по URL
            url_key = r.url.rstrip("/").lower()
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            unique.append(r)

        return unique

    # ── Конвертация ───────────────────────────────────────────────────────────

    @staticmethod
    def _dicts_to_results(data: list[dict]) -> list[SupplierResult]:
        """Преобразует словари из кэша обратно в объекты SupplierResult."""
        results = []
        for d in data:
            results.append(SupplierResult(
                source=d.get("source", ""),
                supplier_name=d.get("supplier_name", ""),
                url=d.get("url", ""),
                price=d.get("price"),
                currency=d.get("currency", "UZS"),
                availability=d.get("availability", False),
                address=d.get("address", ""),
                specs_found=d.get("specs_found", ""),
                has_contacts=d.get("has_contacts", False),
                match_score=d.get("match_score", 0.0),
                rank_score=d.get("rank_score", 0.0),
            ))
        return results
