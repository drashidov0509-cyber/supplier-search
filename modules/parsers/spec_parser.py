"""
Универсальный парсер спецификаций ТМЦ.
Поддерживает Excel (.xlsx, .xls) и PDF с текстовым слоем.
Автоматически определяет структуру таблицы и колонки.
"""

import re
from pathlib import Path
from typing import Optional

import openpyxl
import xlrd
import pdfplumber
from rapidfuzz import fuzz

from config import COLUMN_ALIASES, MAX_POSITIONS, SUPPORTED_EXTENSIONS
from modules.utils.models import SpecItem
from modules.utils.helpers import normalize_text, normalize_unit
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class SpecParser:
    """
    Парсит файл спецификации и возвращает список позиций ТМЦ.
    Поддерживает различные шаблоны таблиц.
    """

    def parse(self, file_path: str | Path) -> list[SpecItem]:
        """
        Основной метод парсинга.
        Определяет формат файла и вызывает нужный парсер.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Неподдерживаемый формат: {suffix}. Допустимые: {SUPPORTED_EXTENSIONS}")

        logger.info("Начало парсинга файла: %s", path.name)

        if suffix in (".xlsx", ".xls"):
            items = self._parse_excel(path)
        elif suffix == ".pdf":
            items = self._parse_pdf(path)
        else:
            items = []

        logger.info("Распознано позиций: %d", len(items))
        return items[:MAX_POSITIONS]

    # ── Excel ─────────────────────────────────────────────────────────────────

    def _parse_excel(self, path: Path) -> list[SpecItem]:
        """Парсит Excel-файл (.xlsx или .xls)."""
        if path.suffix.lower() == ".xlsx":
            return self._parse_xlsx(path)
        else:
            return self._parse_xls(path)

    def _parse_xlsx(self, path: Path) -> list[SpecItem]:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        # Берём первый лист с данными
        ws = wb.active

        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([self._cell_to_str(c) for c in row])

        wb.close()
        return self._extract_items_from_rows(rows)

    def _parse_xls(self, path: Path) -> list[SpecItem]:
        wb = xlrd.open_workbook(str(path))
        ws = wb.sheet_by_index(0)

        rows = []
        for r in range(ws.nrows):
            rows.append([self._cell_to_str(ws.cell_value(r, c)) for c in range(ws.ncols)])

        return self._extract_items_from_rows(rows)

    # ── PDF ───────────────────────────────────────────────────────────────────

    def _parse_pdf(self, path: Path) -> list[SpecItem]:
        """Парсит PDF с текстовым слоем через pdfplumber."""
        all_rows: list[list[str]] = []

        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        cleaned = [self._cell_to_str(c) for c in (row or [])]
                        if any(cleaned):
                            all_rows.append(cleaned)

        if not all_rows:
            logger.warning("В PDF не найдено таблиц: %s", path.name)
            return []

        return self._extract_items_from_rows(all_rows)

    # ── Определение структуры таблицы ─────────────────────────────────────────

    def _extract_items_from_rows(self, rows: list[list[str]]) -> list[SpecItem]:
        """
        Находит строку-заголовок, определяет колонки и извлекает позиции.
        """
        header_idx, col_map = self._detect_header(rows)

        if header_idx is None or not col_map:
            logger.warning("Не удалось определить заголовок таблицы — пробую эвристику")
            return self._heuristic_parse(rows)

        logger.debug("Заголовок найден в строке %d: %s", header_idx, col_map)

        items: list[SpecItem] = []
        row_number = 0

        for row in rows[header_idx + 1 :]:
            name = self._get_col(row, col_map, "name")
            if not name or self._is_header_like(name):
                continue

            # Пропускаем строки с номерами-счётчиками без наименования
            if re.match(r"^\d+\.?$", name.strip()):
                continue

            row_number += 1
            items.append(
                SpecItem(
                    row_number=row_number,
                    name=name.strip(),
                    specs=self._get_col(row, col_map, "specs"),
                    unit=normalize_unit(self._get_col(row, col_map, "unit")),
                    quantity=self._parse_quantity(self._get_col(row, col_map, "quantity")),
                    raw_data={"row": row},
                )
            )

        return items

    def _detect_header(
        self, rows: list[list[str]]
    ) -> tuple[Optional[int], dict[str, int]]:
        """
        Ищет строку-заголовок таблицы.
        Возвращает (индекс строки, маппинг колонок).
        """
        for idx, row in enumerate(rows[:20]):  # Заголовок обычно в первых 20 строках
            col_map = self._match_columns(row)
            if "name" in col_map:
                return idx, col_map

        return None, {}

    def _match_columns(self, header_row: list[str]) -> dict[str, int]:
        """
        Сопоставляет ячейки заголовка с ролями колонок через fuzzy matching.
        """
        col_map: dict[str, int] = {}

        for col_idx, cell in enumerate(header_row):
            cell_norm = normalize_text(cell)
            if not cell_norm:
                continue

            best_role: Optional[str] = None
            best_score = 0

            for role, aliases in COLUMN_ALIASES.items():
                if role in col_map:
                    continue
                for alias in aliases:
                    score = fuzz.token_sort_ratio(cell_norm, alias)
                    if score > best_score and score >= 70:
                        best_score = score
                        best_role = role

            if best_role:
                col_map[best_role] = col_idx

        return col_map

    def _heuristic_parse(self, rows: list[list[str]]) -> list[SpecItem]:
        """
        Эвристический парсинг когда заголовок не найден.
        Считает, что первая непустая колонка — наименование.
        """
        items: list[SpecItem] = []
        row_number = 0

        for row in rows:
            if not row:
                continue
            name = next((c for c in row if c and len(c) > 3), None)
            if not name or self._is_header_like(name):
                continue

            row_number += 1
            items.append(
                SpecItem(
                    row_number=row_number,
                    name=name.strip(),
                    raw_data={"row": row},
                )
            )

        return items

    # ── Вспомогательные ───────────────────────────────────────────────────────

    @staticmethod
    def _get_col(row: list[str], col_map: dict[str, int], role: str) -> str:
        idx = col_map.get(role)
        if idx is None or idx >= len(row):
            return ""
        return row[idx] or ""

    @staticmethod
    def _cell_to_str(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            # Убираем .0 для целых чисел
            return str(int(value)) if value == int(value) else str(value)
        return str(value).strip()

    @staticmethod
    def _parse_quantity(raw: str) -> Optional[float]:
        if not raw:
            return None
        cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _is_header_like(text: str) -> bool:
        """Проверяет не является ли текст строкой заголовка или мусором."""
        header_keywords = [
            "наименование", "название", "характеристики", "единица",
            "количество", "ед.изм", "name", "description", "итого"
        ]
        low = text.lower()
        return any(k in low for k in header_keywords)
