"""Сбор каталога с сайта: категории → страницы списка → товары.

Демонстрационный источник — books.toscrape.com, учебный сайт, созданный для практики парсинга.
Парсер вежливый: ограничение параллельных запросов, пауза между ними, повторы при сбоях.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "price-parser/1.0 (portfolio demo; polite crawler)"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass(frozen=True)
class Product:
    title: str
    category: str
    price: float
    rating: int
    in_stock: bool
    url: str


def parse_categories(html: str, page_url: str) -> list[tuple[str, str]]:
    """Список категорий из бокового меню: (название, абсолютная ссылка)."""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one("div.side_categories ul ul")
    if nav is None:
        return []
    return [(" ".join(a.get_text().split()), urljoin(page_url, a["href"])) for a in nav.select("a")]


def parse_price(raw: str) -> float:
    digits = "".join(ch for ch in raw if ch.isdigit() or ch in ".,").replace(",", ".")
    return float(digits) if digits else 0.0


def parse_listing(html: str, page_url: str, category: str) -> tuple[list[Product], str | None]:
    """Товары со страницы списка и ссылка на следующую страницу (если есть)."""
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        rating_tag = card.select_one("p.star-rating")
        classes = rating_tag.get("class", []) if rating_tag else []
        rating = next((RATINGS[c] for c in classes if c in RATINGS), 0)
        availability = card.select_one("p.availability")
        products.append(
            Product(
                title=link.get("title") or link.get_text(strip=True),
                category=category,
                price=parse_price(card.select_one("p.price_color").get_text()),
                rating=rating,
                in_stock=bool(availability and "in stock" in availability.get_text().lower()),
                url=urljoin(page_url, link["href"]),
            )
        )
    nxt = soup.select_one("li.next a")
    return products, (urljoin(page_url, nxt["href"]) if nxt else None)


async def fetch(client: httpx.AsyncClient, url: str, *, retries: int = 3) -> str:
    """GET с повторами и нарастающей паузой: сайт может временно отвечать ошибкой."""
    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as error:
            if attempt == retries:
                raise
            log.warning("Ошибка %s на %s, повтор %d/%d", error, url, attempt, retries)
            await asyncio.sleep(1.5 * attempt)
    raise RuntimeError("unreachable")


async def scrape(
    base_url: str = BASE_URL,
    *,
    concurrency: int = 5,
    delay: float = 0.2,
    max_categories: int | None = None,
    progress: Callable[[str, int], None] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[Product]:
    """Обходит все категории параллельно (не более `concurrency` запросов одновременно)."""
    own_client = client is None
    client = client or httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
    )
    semaphore = asyncio.Semaphore(concurrency)

    async def polite_fetch(url: str) -> str:
        async with semaphore:
            html = await fetch(client, url)
            await asyncio.sleep(delay)
            return html

    async def crawl_category(name: str, url: str) -> list[Product]:
        found: list[Product] = []
        page: str | None = url
        while page:
            products, page = parse_listing(await polite_fetch(page), page, name)
            found.extend(products)
        if progress:
            progress(name, len(found))
        return found

    try:
        categories = parse_categories(await polite_fetch(base_url), base_url)
        if max_categories:
            categories = categories[:max_categories]
        results = await asyncio.gather(*(crawl_category(n, u) for n, u in categories))
    finally:
        if own_client:
            await client.aclose()

    unique: dict[str, Product] = {}
    for batch in results:
        for product in batch:
            unique.setdefault(product.url, product)
    return sorted(unique.values(), key=lambda p: (p.category, p.title))
