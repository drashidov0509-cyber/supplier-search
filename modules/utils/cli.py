"""
Консольный интерфейс (CLI) системы поиска поставщиков ТМЦ.
Максимально простой интерфейс для специалистов отдела закупок.
"""

import sys
import os
from pathlib import Path

from config import UZBEKISTAN_REGIONS, SUPPORTED_EXTENSIONS, DATA_DIR


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    print("=" * 65)
    print("  СИСТЕМА ПОИСКА И РАНЖИРОВАНИЯ ПОСТАВЩИКОВ ТМЦ")
    print("  Версия 1.0 | Узбекистан")
    print("=" * 65)
    print()


def print_step(step: int, total: int, text: str) -> None:
    print(f"\n[{step}/{total}] {text}")
    print("-" * 50)


def select_file() -> Path:
    """Запрашивает путь к файлу спецификации."""
    print_step(1, 3, "Выбор файла спецификации")

    # Показываем файлы из папки data/
    data_files = []
    for ext in SUPPORTED_EXTENSIONS:
        data_files.extend(DATA_DIR.glob(f"*{ext}"))

    if data_files:
        print(f"\nФайлы в папке data/ ({len(data_files)} найдено):")
        for idx, f in enumerate(data_files, start=1):
            size_kb = f.stat().st_size // 1024
            print(f"  {idx}. {f.name}  ({size_kb} KB)")

        print("\nВведите номер из списка или полный путь к файлу:")
        user_input = input("→ ").strip()

        # Выбор по номеру
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(data_files):
                return data_files[idx]
    else:
        print(f"\nПапка data/ пуста. Поместите файл спецификации (.xlsx, .xls, .pdf) в папку data/")
        print("\nИли введите полный путь к файлу:")
        user_input = input("→ ").strip()

    # Прямой путь
    path = Path(user_input.strip("'\""))
    if not path.exists():
        print(f"\n✗ Файл не найден: {path}")
        sys.exit(1)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        print(f"\n✗ Неподдерживаемый формат. Допустимые: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    return path


def select_region() -> str:
    """Запрашивает регион поиска."""
    print_step(2, 3, "Выбор региона поиска")
    print()

    for idx, region in enumerate(UZBEKISTAN_REGIONS, start=1):
        print(f"  {idx:2d}. {region}")

    print()
    while True:
        user_input = input("Введите номер региона → ").strip()
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(UZBEKISTAN_REGIONS):
                return UZBEKISTAN_REGIONS[idx]
        print("  Введите число от 1 до", len(UZBEKISTAN_REGIONS))


def confirm_search(file_path: Path, region: str, item_count: int) -> bool:
    """Запрашивает подтверждение перед запуском поиска."""
    print_step(3, 3, "Подтверждение параметров")
    print()
    print(f"  Файл:     {file_path.name}")
    print(f"  Регион:   {region}")
    print(f"  Позиций:  {item_count}")
    print()
    print("  Запустить поиск? (д/н) ", end="")
    answer = input().strip().lower()
    return answer in ("д", "y", "да", "yes", "")


class ProgressBar:
    """Простой прогресс-бар для отображения статуса обработки."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.current = 0

    def update(self, current: int, total: int) -> None:
        self.current = current
        pct = int(current / total * 100)
        bar_len = 40
        filled = int(bar_len * current / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"\r  [{bar}] {pct:3d}%  {current}/{total} позиций",
            end="",
            flush=True,
        )
        if current == total:
            print()  # Перевод строки после завершения


def print_results_summary(tasks, report_path: Path) -> None:
    """Выводит итоговую статистику после завершения поиска."""
    found = sum(1 for t in tasks if t.results)
    total = len(tasks)
    found_pct = int(found / total * 100) if total else 0

    print("\n" + "=" * 65)
    print("  ПОИСК ЗАВЕРШЁН")
    print("=" * 65)
    print(f"\n  Всего позиций:    {total}")
    print(f"  Найдено цен:      {found} ({found_pct}%)")
    print(f"  Без результатов:  {total - found}")
    print(f"\n  📄 Отчёт сохранён:")
    print(f"     {report_path}")
    print()
