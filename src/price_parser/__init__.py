"""Парсер каталога с выгрузкой в Excel и отслеживанием изменений цен."""

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path


def main() -> None:
    from price_parser.export import write_csv, write_excel
    from price_parser.history import compare, load_snapshot, save_snapshot
    from price_parser.notify import format_report, send_telegram
    from price_parser.scrape import BASE_URL, scrape

    parser = argparse.ArgumentParser(description="Собирает каталог и выгружает в Excel/CSV")
    parser.add_argument("--out", default="output", help="папка для результатов")
    parser.add_argument("--categories", type=int, default=None, help="ограничить число категорий")
    parser.add_argument("--concurrency", type=int, default=5, help="одновременных запросов")
    parser.add_argument("--notify", action="store_true", help="отчёт в Telegram (TG_BOT_TOKEN, TG_CHAT_ID)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    out = Path(args.out)
    started = time.monotonic()
    print(f"Сбор с {BASE_URL} …")
    products = asyncio.run(
        scrape(
            concurrency=args.concurrency,
            max_categories=args.categories,
            progress=lambda name, count: print(f"  {name}: {count}"),
        )
    )

    snapshot = out / "snapshot.json"
    diff = compare(load_snapshot(snapshot), products)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    xlsx = write_excel(products, diff, out / f"catalog_{stamp}.xlsx", source=BASE_URL)
    csv_path = write_csv(products, out / f"catalog_{stamp}.csv")
    save_snapshot(snapshot, products)

    report = format_report(diff, len(products))
    print(f"\nГотово за {time.monotonic() - started:.1f} с. Товаров: {len(products)}")
    print(f"Excel: {xlsx}\nCSV:   {csv_path}\n\n{report}")

    if args.notify:
        token, chat = os.getenv("TG_BOT_TOKEN"), os.getenv("TG_CHAT_ID")
        if not (token and chat):
            print("Для --notify задайте TG_BOT_TOKEN и TG_CHAT_ID")
        else:
            send_telegram(token, chat, report)
            print("Отчёт отправлен в Telegram")
