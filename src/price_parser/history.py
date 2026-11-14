"""Отслеживание изменений: снимок цен после каждого запуска и сравнение с прошлым."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from price_parser.scrape import Product


@dataclass(frozen=True)
class PriceChange:
    title: str
    url: str
    old_price: float
    new_price: float

    @property
    def delta(self) -> float:
        return round(self.new_price - self.old_price, 2)

    @property
    def percent(self) -> float:
        return round(self.delta / self.old_price * 100, 1) if self.old_price else 0.0


@dataclass(frozen=True)
class Diff:
    changes: list[PriceChange]
    added: list[Product]
    removed: list[str]  # ссылки товаров, которых больше нет

    @property
    def empty(self) -> bool:
        return not (self.changes or self.added or self.removed)


def load_snapshot(path: Path) -> dict[str, dict] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_snapshot(path: Path, products: list[Product]) -> None:
    data = {p.url: {"title": p.title, "price": p.price} for p in products}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def compare(previous: dict[str, dict] | None, products: list[Product]) -> Diff:
    """Первый запуск (previous=None) — изменений нет, всё считается базой."""
    if previous is None:
        return Diff(changes=[], added=[], removed=[])
    current = {p.url: p for p in products}
    changes = [
        PriceChange(p.title, p.url, previous[p.url]["price"], p.price)
        for p in products
        if p.url in previous and abs(previous[p.url]["price"] - p.price) >= 0.005
    ]
    added = [p for p in products if p.url not in previous]
    removed = [url for url in previous if url not in current]
    changes.sort(key=lambda c: c.delta)
    return Diff(changes=changes, added=added, removed=removed)
