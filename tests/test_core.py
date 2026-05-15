"""
Тесты для ключевых модулей системы.
Запуск: python -m pytest tests/ -v
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Тесты helpers.py ────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_lowercase(self):
        from modules.utils.helpers import normalize_text
        assert normalize_text("КАБЕЛЬ ВВГ") == "кабель ввг"

    def test_extra_spaces(self):
        from modules.utils.helpers import normalize_text
        assert normalize_text("  кабель   ввг  ") == "кабель ввг"

    def test_cyrillic_x_to_latin(self):
        from modules.utils.helpers import normalize_text
        result = normalize_text("3х2.5")
        assert "x" in result  # кириллическая х → латинская

    def test_empty_string(self):
        from modules.utils.helpers import normalize_text
        assert normalize_text("") == ""

    def test_none_like(self):
        from modules.utils.helpers import normalize_text
        assert normalize_text("   ") == ""


class TestNormalizeUnit:
    def test_штук(self):
        from modules.utils.helpers import normalize_unit
        assert normalize_unit("штука") == "шт"

    def test_метр(self):
        from modules.utils.helpers import normalize_unit
        assert normalize_unit("метр") == "м"

    def test_unknown_unit(self):
        from modules.utils.helpers import normalize_unit
        assert normalize_unit("кг") == "кг"


class TestFuzzyMatch:
    def test_exact_match(self):
        from modules.utils.helpers import fuzzy_match_score
        score = fuzzy_match_score("кабель ввг 3х2.5", "кабель ввг 3х2.5")
        assert score == 100.0

    def test_similar_names(self):
        from modules.utils.helpers import fuzzy_match_score
        # Ключевой тест из ТЗ
        score = fuzzy_match_score(
            "Кабель ВВГнг 3х2.5",
            "Кабель силовой ВВГнг-LS 3x2,5"
        )
        assert score >= 65, f"Ожидали ≥65, получили {score}"

    def test_completely_different(self):
        from modules.utils.helpers import fuzzy_match_score
        score = fuzzy_match_score("кабель", "насос центробежный")
        assert score < 50

    def test_is_similar_true(self):
        from modules.utils.helpers import is_similar
        assert is_similar("Труба стальная DN50", "Труба стальная Ду50")

    def test_is_similar_false(self):
        from modules.utils.helpers import is_similar
        assert not is_similar("кабель", "цемент марка 500")


class TestParsePrice:
    def test_integer_price(self):
        from modules.utils.helpers import parse_price
        assert parse_price("150000") == 150000.0

    def test_spaced_price(self):
        from modules.utils.helpers import parse_price
        assert parse_price("1 500 000") == 1500000.0

    def test_decimal_comma(self):
        from modules.utils.helpers import parse_price
        assert parse_price("45,50") == 45.50

    def test_with_currency(self):
        from modules.utils.helpers import parse_price
        assert parse_price("150 000 сум") == 150000.0

    def test_empty(self):
        from modules.utils.helpers import parse_price
        assert parse_price("") is None

    def test_none_like(self):
        from modules.utils.helpers import parse_price
        assert parse_price("нет цены") is None


# ─── Тесты ranker.py ─────────────────────────────────────────────────────────

class TestRanker:
    def _make_result(self, price=None, available=True, match=0.8, contacts=False):
        from modules.utils.models import SupplierResult
        return SupplierResult(
            source="test",
            supplier_name="Test Supplier",
            url="https://test.uz",
            price=price,
            availability=available,
            match_score=match,
            has_contacts=contacts,
        )

    def test_cheaper_ranks_higher(self):
        from modules.ranking.ranker import Ranker
        ranker = Ranker()
        cheap = self._make_result(price=100_000)
        expensive = self._make_result(price=500_000)
        ranked = ranker.rank([expensive, cheap])
        assert ranked[0].price == 100_000

    def test_available_ranks_higher(self):
        from modules.ranking.ranker import Ranker
        ranker = Ranker()
        available = self._make_result(price=200_000, available=True)
        unavailable = self._make_result(price=200_000, available=False)
        ranked = ranker.rank([unavailable, available])
        assert ranked[0].availability is True

    def test_empty_list(self):
        from modules.ranking.ranker import Ranker
        ranker = Ranker()
        assert ranker.rank([]) == []

    def test_single_result(self):
        from modules.ranking.ranker import Ranker
        ranker = Ranker()
        result = self._make_result(price=100_000)
        ranked = ranker.rank([result])
        assert len(ranked) == 1
        assert ranked[0].rank_score > 0

    def test_no_price_gets_neutral_score(self):
        from modules.ranking.ranker import Ranker
        ranker = Ranker()
        no_price = self._make_result(price=None)
        with_price = self._make_result(price=100_000)
        ranked = ranker.rank([no_price, with_price])
        # Результат с ценой должен быть выше
        assert ranked[0].price == 100_000


# ─── Тесты spec_parser.py ────────────────────────────────────────────────────

class TestColumnDetection:
    def test_detect_name_column(self):
        from modules.parsers.spec_parser import SpecParser
        parser = SpecParser()
        header = ["№", "Наименование", "Марка", "Ед.изм", "Кол-во"]
        col_map = parser._match_columns(header)
        assert "name" in col_map
        assert col_map["name"] == 1

    def test_detect_quantity_column(self):
        from modules.parsers.spec_parser import SpecParser
        parser = SpecParser()
        header = ["Название", "Характеристики", "Единица", "Количество"]
        col_map = parser._match_columns(header)
        assert "quantity" in col_map

    def test_english_headers(self):
        from modules.parsers.spec_parser import SpecParser
        parser = SpecParser()
        header = ["Item Name", "Specification", "Unit", "Qty"]
        col_map = parser._match_columns(header)
        assert "name" in col_map


class TestSpecParser:
    def test_parse_simple_rows(self):
        from modules.parsers.spec_parser import SpecParser
        parser = SpecParser()
        rows = [
            ["№", "Наименование", "Ед.изм", "Кол-во"],
            ["1", "Кабель ВВГнг 3х2.5", "м", "100"],
            ["2", "Труба стальная DN50", "шт", "20"],
        ]
        items = parser._extract_items_from_rows(rows)
        assert len(items) == 2
        assert items[0].name == "Кабель ВВГнг 3х2.5"
        assert items[0].unit == "м"
        assert items[0].quantity == 100.0
        assert items[1].name == "Труба стальная DN50"

    def test_skip_empty_rows(self):
        from modules.parsers.spec_parser import SpecParser
        parser = SpecParser()
        rows = [
            ["Наименование", "Кол-во"],
            ["Кабель ВВГ", "10"],
            ["", ""],
            ["Труба", "5"],
        ]
        items = parser._extract_items_from_rows(rows)
        assert len(items) == 2


# ─── Тесты database.py ───────────────────────────────────────────────────────

class TestDatabase:
    @pytest.fixture(autouse=True)
    def use_temp_db(self, tmp_path, monkeypatch):
        """Перенаправляем БД во временную директорию."""
        import config
        monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "test.db")

    def test_init_and_session(self):
        from modules.database.db import init_database, create_session, finish_session
        init_database()
        session_id = create_session("test.xlsx", "Ташкент")
        assert session_id > 0
        finish_session(session_id, total=10, found=8)

    def test_cache_set_get(self):
        from modules.database.db import init_database, cache_set, cache_get
        init_database()
        data = [{"price": 100, "supplier": "Test"}]
        cache_set("test_key", data)
        result = cache_get("test_key")
        assert result is not None
        assert result[0]["price"] == 100

    def test_cache_miss(self):
        from modules.database.db import init_database, cache_get
        init_database()
        result = cache_get("nonexistent_key")
        assert result is None


# ─── Тесты SearchEngine (unit, без реального HTTP) ───────────────────────────

class TestSearchEngine:
    def test_deduplication(self):
        from modules.search.engine import SearchEngine
        from modules.utils.models import SupplierResult

        engine = SearchEngine.__new__(SearchEngine)

        results = [
            SupplierResult(source="a", supplier_name="S1", url="https://test.uz/item/1"),
            SupplierResult(source="b", supplier_name="S2", url="https://test.uz/item/1"),  # дубль
            SupplierResult(source="c", supplier_name="S3", url="https://test.uz/item/2"),
        ]
        unique = SearchEngine._deduplicate(results)
        assert len(unique) == 2

    def test_dicts_to_results(self):
        from modules.search.engine import SearchEngine

        data = [{"source": "prom_uz", "supplier_name": "ООО Тест", "url": "https://prom.uz/1", "price": 50000}]
        results = SearchEngine._dicts_to_results(data)
        assert len(results) == 1
        assert results[0].supplier_name == "ООО Тест"
        assert results[0].price == 50000
