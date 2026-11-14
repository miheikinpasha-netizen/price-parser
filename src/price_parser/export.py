"""Выгрузка в Excel (оформленная таблица + сводка + изменения) и CSV."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from price_parser.history import Diff
from price_parser.scrape import Product

HEADER_FILL = PatternFill("solid", fgColor="1D1D1F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
UP_FONT = Font(color="C62828")
DOWN_FONT = Font(color="2E7D32")
PRICE_FORMAT = '"£"#,##0.00'


def stars(rating: int) -> str:
    return "★" * rating + "☆" * (5 - rating)


def _header(ws: Worksheet, titles: list[str], widths: list[int]) -> None:
    ws.append(titles)
    for col, width in enumerate(widths, start=1):
        cell = ws.cell(row=1, column=col)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"


def write_excel(products: list[Product], diff: Diff, path: Path, *, source: str) -> Path:
    wb = Workbook()

    # Лист 1: весь каталог
    ws = wb.active
    ws.title = "Каталог"
    _header(ws, ["Название", "Категория", "Цена", "Рейтинг", "В наличии", "Ссылка"], [52, 22, 11, 11, 11, 60])
    for p in products:
        ws.append([p.title, p.category, p.price, stars(p.rating), "да" if p.in_stock else "нет", p.url])
        row = ws.max_row
        ws.cell(row=row, column=3).number_format = PRICE_FORMAT
        link = ws.cell(row=row, column=6)
        link.hyperlink, link.style = p.url, "Hyperlink"
    ws.auto_filter.ref = f"A1:F{ws.max_row}"

    # Лист 2: сводка по категориям
    summary = wb.create_sheet("Сводка")
    _header(summary, ["Категория", "Товаров", "Средняя цена", "Мин. цена", "Макс. цена", "Ср. рейтинг"], [26, 10, 14, 12, 12, 12])
    by_category: dict[str, list[Product]] = defaultdict(list)
    for p in products:
        by_category[p.category].append(p)
    for name, items in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        prices = [i.price for i in items]
        summary.append([
            name, len(items), round(sum(prices) / len(prices), 2), min(prices), max(prices),
            round(sum(i.rating for i in items) / len(items), 1),
        ])
        for col in (3, 4, 5):
            summary.cell(row=summary.max_row, column=col).number_format = PRICE_FORMAT
    summary.append([])
    summary.append(["Всего товаров", len(products)])
    summary.append(["Источник", source])
    summary.append(["Собрано", datetime.now().strftime("%d.%m.%Y %H:%M")])

    # Лист 3: изменения с прошлого запуска
    changes = wb.create_sheet("Изменения цен")
    _header(changes, ["Название", "Было", "Стало", "Разница", "%", "Ссылка"], [52, 10, 10, 10, 8, 60])
    for c in diff.changes:
        changes.append([c.title, c.old_price, c.new_price, c.delta, c.percent, c.url])
        row = changes.max_row
        for col in (2, 3, 4):
            changes.cell(row=row, column=col).number_format = PRICE_FORMAT
        font = UP_FONT if c.delta > 0 else DOWN_FONT
        changes.cell(row=row, column=4).font = font
        changes.cell(row=row, column=5).font = font
    if diff.empty:
        changes.append(["Изменений нет (или это первый запуск — он становится базой для сравнения)"])
    else:
        changes.append([])
        changes.append([f"Новых товаров: {len(diff.added)}, пропало: {len(diff.removed)}"])

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def write_csv(products: list[Product], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig — Excel откроет без «кракозябр»
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["title", "category", "price", "rating", "in_stock", "url"])
        for p in products:
            writer.writerow([p.title, p.category, f"{p.price:.2f}", p.rating, int(p.in_stock), p.url])
    return path
