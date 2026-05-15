#!/usr/bin/env python3
"""
Система автоматизации поиска и ранжирования поставщиков ТМЦ.
Точка входа в приложение.

Запуск:
    python main.py
"""

import sys
import traceback
from pathlib import Path

# Инициализируем логирование в самом начале
from modules.logging.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    """
    Главная функция. Оркестрирует весь процесс:
    1. CLI — выбор файла и региона
    2. Парсинг спецификации
    3. Поиск по источникам (параллельно)
    4. Ранжирование результатов
    5. Формирование Excel-отчёта
    6. Сохранение в БД
    """
    # Импорты здесь чтобы логирование уже было настроено
    from modules.utils.cli import (
        clear_screen, print_banner,
        select_file, select_region, confirm_search,
        ProgressBar, print_results_summary,
    )
    from modules.parsers.spec_parser import SpecParser
    from modules.search.engine import SearchEngine
    from modules.ranking.ranker import Ranker
    from modules.exporters.excel_exporter import ExcelExporter
    from modules.database.db import (
        init_database, create_session, finish_session,
        save_spec_items, save_search_result, cache_cleanup,
        log_operation,
    )

    clear_screen()
    print_banner()

    # ── Инициализация БД ──────────────────────────────────────────────────────
    try:
        init_database()
        cache_cleanup()
    except Exception as e:
        logger.critical("Ошибка инициализации базы данных: %s", e)
        print(f"\n✗ Ошибка БД: {e}")
        return 1

    # ── Выбор файла ───────────────────────────────────────────────────────────
    try:
        file_path = select_file()
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        return 0

    # ── Парсинг спецификации ──────────────────────────────────────────────────
    print(f"\n  Читаем файл: {file_path.name} ...", end=" ", flush=True)
    try:
        parser = SpecParser()
        items = parser.parse(file_path)
    except FileNotFoundError as e:
        print(f"\n✗ {e}")
        return 1
    except Exception as e:
        logger.error("Ошибка парсинга файла: %s", e)
        print(f"\n✗ Ошибка чтения файла: {e}")
        return 1

    if not items:
        print("\n✗ В файле не найдено позиций ТМЦ.")
        print("  Убедитесь что файл содержит таблицу с наименованиями.")
        return 1

    print(f"OK ({len(items)} позиций)")

    # ── Выбор региона ─────────────────────────────────────────────────────────
    try:
        region = select_region()
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        return 0

    # ── Подтверждение ─────────────────────────────────────────────────────────
    try:
        if not confirm_search(file_path, region, len(items)):
            print("\n  Операция отменена.")
            return 0
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        return 0

    # ── Создание сессии в БД ──────────────────────────────────────────────────
    session_id = create_session(str(file_path), region)
    item_ids = save_spec_items(session_id, [
        {
            "row_number": item.row_number,
            "name": item.name,
            "specs": item.specs,
            "unit": item.unit,
            "quantity": item.quantity,
        }
        for item in items
    ])

    # Привязываем db_id к объектам
    for item, db_id in zip(items, item_ids):
        item.db_id = db_id

    # ── Поиск ─────────────────────────────────────────────────────────────────
    print(f"\n  Запуск поиска по {len(items)} позициям...")
    print(f"  Регион: {region}")
    print()

    progress = ProgressBar(len(items))

    try:
        engine = SearchEngine()
        tasks = engine.search_all(items, region, progress_callback=progress.update)
    except KeyboardInterrupt:
        print("\n\n  Поиск прерван пользователем.")
        finish_session(session_id, len(items), 0, status="interrupted")
        return 0
    except Exception as e:
        logger.critical("Критическая ошибка поиска: %s\n%s", e, traceback.format_exc())
        print(f"\n✗ Критическая ошибка: {e}")
        finish_session(session_id, len(items), 0, status="error")
        return 1

    # ── Ранжирование ──────────────────────────────────────────────────────────
    print("\n  Ранжирование результатов...", end=" ", flush=True)
    ranker = Ranker()
    tasks = ranker.rank_tasks(tasks)
    print("OK")

    # ── Сохранение результатов в БД ───────────────────────────────────────────
    print("  Сохранение в базу данных...", end=" ", flush=True)
    found_count = 0
    for task in tasks:
        if task.results and task.spec_item.db_id:
            found_count += 1
            for result in task.results[:5]:  # Сохраняем топ-5 вариантов
                save_search_result(task.spec_item.db_id, result.to_dict())

    finish_session(session_id, len(items), found_count)
    print("OK")

    # ── Формирование отчёта ───────────────────────────────────────────────────
    print("  Формирование Excel-отчёта...", end=" ", flush=True)
    try:
        exporter = ExcelExporter()
        report_path = exporter.export(tasks, region)
        print("OK")
    except Exception as e:
        logger.error("Ошибка формирования отчёта: %s", e)
        print(f"\n✗ Ошибка отчёта: {e}")
        return 1

    # ── Итоги ─────────────────────────────────────────────────────────────────
    print_results_summary(tasks, report_path)
    log_operation(session_id, "INFO", f"Отчёт сформирован: {report_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nРабота завершена.")
        sys.exit(0)
    except Exception as e:
        logger.critical("Неожиданная критическая ошибка: %s", e, exc_info=True)
        print(f"\n✗ Критическая ошибка: {e}")
        sys.exit(1)
