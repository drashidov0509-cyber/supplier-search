"""
Конфигурация системы поиска и ранжирования поставщиков ТМЦ.
Все настройки системы централизованы здесь.
"""

from pathlib import Path
from typing import Optional
import os

# ─── Пути проекта ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"
DATABASE_DIR = BASE_DIR / "database"

# Создаём директории если не существуют
for _dir in [DATA_DIR, OUTPUT_DIR, LOGS_DIR, CACHE_DIR, DATABASE_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─── База данных ──────────────────────────────────────────────────────────────

DATABASE_PATH = DATABASE_DIR / "supplier_search.db"

# ─── Логирование ─────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# ─── Поиск и скрапинг ────────────────────────────────────────────────────────

# Количество потоков для параллельного поиска
MAX_WORKERS = 5

# Таймаут HTTP-запросов (секунды)
REQUEST_TIMEOUT = 15

# Задержка между запросами к одному сайту (секунды)
REQUEST_DELAY_MIN = 1.0
REQUEST_DELAY_MAX = 3.0

# Количество повторных попыток при ошибке
MAX_RETRIES = 3

# Задержка между retry (секунды)
RETRY_DELAY = 2.0

# Максимум результатов на один запрос с одного источника
MAX_RESULTS_PER_SOURCE = 10

# Кэш результатов поиска (часы)
CACHE_TTL_HOURS = 24

# ─── Прокси ───────────────────────────────────────────────────────────────────

# Список прокси (формат: "http://user:pass@host:port" или "http://host:port")
# Можно задать через переменную окружения PROXY_LIST (через запятую)
PROXY_LIST: list[str] = [
    proxy.strip()
    for proxy in os.getenv("PROXY_LIST", "").split(",")
    if proxy.strip()
]

# Таймаут проверки прокси
PROXY_CHECK_TIMEOUT = 10

# ─── Playwright / Selenium ────────────────────────────────────────────────────

# Использовать headless-браузер как fallback
USE_PLAYWRIGHT_FALLBACK = True

# Таймаут браузера (миллисекунды)
BROWSER_TIMEOUT = 30_000

# User-Agent для requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

# ─── Нормализация и fuzzy matching ───────────────────────────────────────────

# Минимальный порог схожести для fuzzy matching (0-100)
FUZZY_MATCH_THRESHOLD = 65

# ─── Ранжирование ────────────────────────────────────────────────────────────

# Веса критериев ранжирования (в сумме = 1.0)
RANKING_WEIGHTS = {
    "price": 0.50,           # Минимальная цена
    "availability": 0.25,    # Наличие товара
    "match_score": 0.15,     # Совпадение характеристик
    "contacts": 0.10,        # Наличие контактов
}

# ─── Регионы Узбекистана ──────────────────────────────────────────────────────

UZBEKISTAN_REGIONS = [
    "Ташкент",
    "Ташкентская область",
    "Самарканд",
    "Бухара",
    "Навои",
    "Фергана",
    "Андижан",
    "Наманган",
    "Джизак",
    "Сырдарья",
    "Кашкадарья",
    "Сурхандарья",
    "Хорезм",
    "Республика Каракалпакстан",
]

# ─── Источники поиска ────────────────────────────────────────────────────────

# Включённые источники (можно отключить проблемные)
ENABLED_SOURCES = [
    "prom_uz",
    "olx_uz",
    "glotr_uz",
    "stroyka_uz",
]

# ─── Парсинг файлов ───────────────────────────────────────────────────────────

# Поддерживаемые расширения
SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".pdf"]

# Максимальное количество позиций для обработки
MAX_POSITIONS = 10_000

# Имена колонок для автоопределения (lowercase, fuzzy)
COLUMN_ALIASES = {
    "name": [
        "наименование", "название", "товар", "материал", "тмц",
        "name", "item name", "item", "description", "номенклатура", "позиция"
    ],
    "specs": [
        "характеристики", "марка", "тип", "артикул", "спецификация",
        "spec", "brand", "type", "article", "техническое описание"
    ],
    "unit": [
        "ед", "единица", "ед.изм", "unit", "мера", "ед. изм.", "уп"
    ],
    "quantity": [
        "количество", "кол-во", "qty", "quantity", "кол", "объем", "объём"
    ],
}

# ─── Отчёт Excel ─────────────────────────────────────────────────────────────

REPORT_COLUMNS = [
    "№ п/п",
    "Наименование ТМЦ",
    "Технические характеристики / марка",
    "Ед. изм.",
    "Объем (количество)",
    "Цена за единицу с НДС",
    "Итоговая стоимость с НДС",
    "Поставщик",
    "Адрес поставщика",
    "Ссылка на сайт поставщика",
    "Наличие",
    "Примечание",
]

# Цвета для Excel-отчёта
EXCEL_COLORS = {
    "header_bg": "1F4E79",
    "header_fg": "FFFFFF",
    "best_offer_bg": "E2EFDA",   # Зелёный — лучшее предложение
    "alt_row_bg": "F2F2F2",      # Чередующиеся строки
    "hyperlink_color": "0563C1",
}
