"""
Модели данных (dataclasses).
Единственный источник истины для структур данных системы.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpecItem:
    """Одна позиция из спецификации ТМЦ."""
    row_number: int
    name: str
    specs: str = ""
    unit: str = ""
    quantity: Optional[float] = None
    raw_data: dict = field(default_factory=dict)

    # Заполняется после сохранения в БД
    db_id: Optional[int] = None

    def search_query(self) -> str:
        """Формирует строку запроса для поиска."""
        parts = [self.name]
        if self.specs:
            parts.append(self.specs)
        return " ".join(parts).strip()


@dataclass
class SupplierResult:
    """Результат поиска одного предложения от поставщика."""
    source: str
    supplier_name: str
    url: str

    price: Optional[float] = None
    currency: str = "UZS"
    availability: bool = False
    address: str = ""
    specs_found: str = ""
    has_contacts: bool = False

    # Вычисляется позже
    match_score: float = 0.0
    rank_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "supplier_name": self.supplier_name,
            "url": self.url,
            "price": self.price,
            "currency": self.currency,
            "availability": self.availability,
            "address": self.address,
            "specs_found": self.specs_found,
            "has_contacts": self.has_contacts,
            "match_score": self.match_score,
            "rank_score": self.rank_score,
        }


@dataclass
class SearchTask:
    """Задача поиска для одной позиции спецификации."""
    spec_item: SpecItem
    region: str
    results: list[SupplierResult] = field(default_factory=list)
    error: Optional[str] = None
    from_cache: bool = False


@dataclass
class ReportRow:
    """Строка итогового Excel-отчёта."""
    number: int
    name: str
    specs: str
    unit: str
    quantity: Optional[float]
    price: Optional[float]
    total_price: Optional[float]
    supplier_name: str
    supplier_address: str
    supplier_url: str
    availability: str
    note: str = ""
