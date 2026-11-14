"""Уведомление об изменениях цен в Telegram (необязательно: нужен токен бота и chat_id)."""

from __future__ import annotations

import httpx

from price_parser.history import Diff


def format_report(diff: Diff, total: int, limit: int = 10) -> str:
    if diff.empty:
        return f"Парсер: собрано {total} товаров, изменений цен нет."
    lines = [f"Парсер: собрано {total} товаров.", f"Изменилось цен: {len(diff.changes)}"]
    for c in diff.changes[:limit]:
        arrow = "▲" if c.delta > 0 else "▼"
        lines.append(f"{arrow} {c.title[:40]}: £{c.old_price:.2f} → £{c.new_price:.2f} ({c.percent:+.1f}%)")
    if len(diff.changes) > limit:
        lines.append(f"…и ещё {len(diff.changes) - limit} — полный список в Excel")
    if diff.added or diff.removed:
        lines.append(f"Новых товаров: {len(diff.added)}, пропало: {len(diff.removed)}")
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
