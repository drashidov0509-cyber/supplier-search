# Система поиска и ранжирования поставщиков ТМЦ

Автоматизированный инструмент для отдела закупок: загружает спецификацию ТМЦ, ищет поставщиков на узбекских торговых площадках, ранжирует по цене и выдаёт готовый Excel-отчёт.

---

## Возможности

- **Импорт** спецификаций из Excel (`.xlsx`, `.xls`) и PDF
- **Автоопределение** структуры таблицы — не нужно настраивать шаблон
- **Поиск** на Prom.uz, OLX.uz, Glotr.uz, Stroyka.uz (параллельно)
- **Fuzzy matching** — находит «Кабель ВВГнг 3х2.5» и «Кабель силовой ВВГнг-LS 3x2,5» как одно
- **Ранжирование** по цене, наличию, совпадению характеристик
- **Кэш** результатов на 24 часа — повторный поиск работает мгновенно
- **Excel-отчёт** с гиперссылками, условным форматированием и автофильтром
- **SQLite** база данных с историей всех поисков
- Поддержка **прокси** для обхода блокировок
- **Playwright** как автоматический fallback при блокировке обычных запросов

---

## Требования

- Python **3.12+**
- Windows 10/11 или Linux (Ubuntu 20.04+)
- Интернет-соединение
- ~500 MB места на диске (Playwright + Chromium)

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/drashidov0509-cyber/supplier-search.git
cd supplier-search
```

### 2. Создать виртуальное окружение (рекомендуется)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Установить браузер Playwright (один раз)

```bash
playwright install chromium
```

---

## Запуск

```bash
python main.py
```

Программа в интерактивном режиме попросит:
1. Выбрать файл спецификации
2. Выбрать регион
3. Подтвердить запуск

Пример сессии:
```
=================================================================
  СИСТЕМА ПОИСКА И РАНЖИРОВАНИЯ ПОСТАВЩИКОВ ТМЦ
  Версия 1.0 | Узбекистан
=================================================================

[1/3] Выбор файла спецификации
--------------------------------------------------
Файлы в папке data/ (1 найдено):
  1. specification_2024.xlsx  (48 KB)

Введите номер из списка или полный путь к файлу:
→ 1

  Читаем файл: specification_2024.xlsx ... OK (42 позиции)

[2/3] Выбор региона поиска
  1. Ташкент
  2. Ташкентская область
  ...

Введите номер региона → 1

[3/3] Подтверждение параметров
  Файл:     specification_2024.xlsx
  Регион:   Ташкент
  Позиций:  42

  Запустить поиск? (д/н) д

  Запуск поиска по 42 позициям...
  [████████████████████░░░░░░░░░░░░░░░░░░░░]  52%  22/42 позиций

=================================================================
  ПОИСК ЗАВЕРШЁН
=================================================================
  Всего позиций:    42
  Найдено цен:      38 (90%)
  Без результатов:  4

  📄 Отчёт сохранён:
     output/report_Ташкент_20240615_143022.xlsx
```

---

## Структура проекта

```
supplier_search/
│
├── main.py                  # Точка входа
├── config.py                # Все настройки системы
├── requirements.txt         # Зависимости Python
├── README.md
├── .gitignore
│
├── modules/
│   ├── parsers/
│   │   └── spec_parser.py   # Парсер Excel и PDF спецификаций
│   │
│   ├── search/
│   │   ├── base_scraper.py  # Базовый класс для источников
│   │   ├── registry.py      # Реестр источников (плагин-система)
│   │   ├── engine.py        # Поисковый движок (параллельный)
│   │   ├── prom_uz.py       # Скрапер Prom.uz
│   │   ├── olx_uz.py        # Скрапер OLX.uz
│   │   └── other_scrapers.py# Glotr.uz, Stroyka.uz
│   │
│   ├── ranking/
│   │   └── ranker.py        # Ранжирование поставщиков
│   │
│   ├── exporters/
│   │   └── excel_exporter.py# Формирование Excel-отчёта
│   │
│   ├── database/
│   │   └── db.py            # SQLite: сессии, результаты, кэш
│   │
│   ├── utils/
│   │   ├── models.py        # Dataclasses (SpecItem, SupplierResult…)
│   │   ├── helpers.py       # Нормализация, fuzzy matching, прокси
│   │   ├── http_client.py   # HTTP с retry + Playwright fallback
│   │   └── cli.py           # Консольный интерфейс
│   │
│   └── logging/
│       └── logger.py        # Настройка логирования
│
├── data/                    # 📥 Сюда кладите файлы спецификаций
├── output/                  # 📤 Сюда сохраняются Excel-отчёты
├── logs/                    # Логи (app.log, errors.log, search.log)
├── cache/                   # Не используется напрямую (кэш в SQLite)
└── database/                # supplier_search.db
```

---

## Конфигурация

Все параметры находятся в `config.py`. Основные:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `MAX_WORKERS` | `5` | Потоков для параллельного поиска |
| `REQUEST_TIMEOUT` | `15` | Таймаут HTTP-запроса (сек) |
| `CACHE_TTL_HOURS` | `24` | Время жизни кэша (часы) |
| `FUZZY_MATCH_THRESHOLD` | `65` | Порог схожести 0–100 |
| `MAX_RESULTS_PER_SOURCE` | `10` | Результатов с одного сайта |
| `ENABLED_SOURCES` | все | Список активных источников |

### Прокси

Через переменную окружения:
```bash
# Linux
export PROXY_LIST="http://user:pass@host1:3128,http://host2:3128"
python main.py

# Windows
set PROXY_LIST=http://user:pass@host1:3128,http://host2:3128
python main.py
```

Или через `.env` файл (создайте в корне проекта):
```env
PROXY_LIST=http://user:pass@host1:3128,http://host2:3128
LOG_LEVEL=DEBUG
```

### Уровень логирования

```bash
LOG_LEVEL=DEBUG python main.py   # Подробные логи
LOG_LEVEL=WARNING python main.py # Только предупреждения и ошибки
```

---

## Добавление нового источника

1. Создайте файл `modules/search/my_source.py`:

```python
from modules.search.base_scraper import BaseScraper
from modules.utils.models import SupplierResult

class MySourceScraper(BaseScraper):
    source_id = "my_source"
    source_name = "Мой источник"
    base_url = "https://my-source.uz"

    def search(self, query: str, region: str) -> list[SupplierResult]:
        url = self._build_search_url(query, region)
        html = self._fetch_page(url)
        if not html:
            return []
        return self._parse_results(html, query)

    def _build_search_url(self, query: str, region: str) -> str:
        return f"{self.base_url}/search?q={query}"

    def _parse_results(self, html: str, query: str) -> list[SupplierResult]:
        soup = self._soup(html)
        results = []
        # ... ваша логика парсинга ...
        return results
```

2. Зарегистрируйте в `modules/search/registry.py`:

```python
from modules.search.my_source import MySourceScraper

_SCRAPER_REGISTRY = {
    ...
    "my_source": MySourceScraper,  # добавить сюда
}
```

3. Включите в `config.py`:

```python
ENABLED_SOURCES = [
    "prom_uz",
    "olx_uz",
    "my_source",  # добавить сюда
]
```

---

## Формат отчёта

Отчёт сохраняется в `output/report_{регион}_{дата}.xlsx`.

| Колонка | Описание |
|---|---|
| № п/п | Порядковый номер |
| Наименование ТМЦ | Из спецификации |
| Технические характеристики | Из спецификации |
| Ед. изм. | Единица измерения |
| Объем | Количество |
| Цена за единицу с НДС | Лучшая найденная цена |
| Итоговая стоимость с НДС | Цена × Количество |
| Поставщик | Название компании |
| Адрес поставщика | Адрес или город |
| Ссылка на сайт | Активная гиперссылка |
| Наличие | «В наличии» / «Под заказ» |
| Примечание | Кол-во найденных вариантов |

- 🟢 Зелёная подсветка — лучшие предложения (есть цена + в наличии)
- Второй лист «Сводка» — быстрый обзор по всем позициям
- Автофильтр включён на всех колонках

---

## Возможные ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Файл не найден` | Неверный путь | Проверьте путь, поместите файл в `data/` |
| `Неподдерживаемый формат` | Не .xlsx/.xls/.pdf | Конвертируйте файл |
| `В файле не найдено позиций` | Нет таблицы или PDF без текста | Убедитесь что PDF содержит текстовый слой |
| `Ошибка БД` | Нет прав на запись | Запустите от имени пользователя с правами записи |
| `Таймаут поиска` | Медленный интернет или блокировка | Настройте прокси, увеличьте `REQUEST_TIMEOUT` |
| `Playwright ошибка` | Chromium не установлен | Запустите `playwright install chromium` |
| `0% найдено` | Все сайты заблокированы | Добавьте прокси в `PROXY_LIST` |

### Логи для диагностики

```
logs/app.log      — общий журнал операций
logs/errors.log   — только ошибки
logs/search.log   — детальный лог поиска (запросы, источники)
```

---

## Ограничения текущей версии

- OCR сканированных PDF не поддерживается
- Зависит от актуальности HTML-структуры сайтов (может потребовать обновления при редизайне)
- 100% совпадение характеристик не гарантируется
- Работает только с открытыми данными

---

## Репозиторий

https://github.com/drashidov0509-cyber/supplier-search

---

## Лицензия

MIT
