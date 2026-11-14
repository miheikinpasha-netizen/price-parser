"""Тесты без сети: разбор HTML, сравнение снимков, выгрузка в Excel."""

from openpyxl import load_workbook

from price_parser.export import stars, write_csv, write_excel
from price_parser.history import compare, load_snapshot, save_snapshot
from price_parser.notify import format_report
from price_parser.scrape import Product, parse_categories, parse_listing, parse_price

PAGE = "https://example.test/catalogue/category/books/travel_2/index.html"
LISTING = """
<ol>
<article class="product_pod"><h3><a href="../../../a-trip_1/index.html" title="A Trip">A Tr...</a></h3>
<p class="star-rating Four"></p><p class="price_color">£45.17</p>
<p class="instock availability"> In stock </p></article>
<article class="product_pod"><h3><a href="../../../b-road_2/index.html" title="B Road">B Road</a></h3>
<p class="star-rating One"></p><p class="price_color">£9.00</p>
<p class="availability">Out of stock</p></article>
</ol>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
"""
HOME = """<div class="side_categories"><ul><li><a href="x">Books</a><ul>
<li><a href="catalogue/category/books/travel_2/index.html"> Travel </a></li>
<li><a href="catalogue/category/books/mystery_3/index.html">Mystery</a></li></ul></li></ul></div>"""


def product(url="u1", price=10.0, title="T"):
    return Product(title=title, category="C", price=price, rating=3, in_stock=True, url=url)


def test_parse_categories_resolves_links():
    assert parse_categories(HOME, "https://example.test/") == [
        ("Travel", "https://example.test/catalogue/category/books/travel_2/index.html"),
        ("Mystery", "https://example.test/catalogue/category/books/mystery_3/index.html"),
    ]


def test_parse_listing_fields_and_next_page():
    products, nxt = parse_listing(LISTING, PAGE, "Travel")
    assert [p.title for p in products] == ["A Trip", "B Road"]
    assert products[0].price == 45.17 and products[0].rating == 4 and products[0].in_stock
    assert products[1].rating == 1 and not products[1].in_stock
    assert products[0].url == "https://example.test/catalogue/a-trip_1/index.html"
    assert nxt == "https://example.test/catalogue/category/books/travel_2/page-2.html"
    assert parse_listing("<html></html>", PAGE, "X") == ([], None)


def test_parse_price_formats():
    assert parse_price("£51.77") == 51.77
    assert parse_price("1 299,50 ₽") == 1299.5
    assert parse_price("—") == 0.0


def test_compare_first_run_is_baseline_and_detects_changes(tmp_path):
    assert compare(None, [product()]).empty
    snap = tmp_path / "s.json"
    save_snapshot(snap, [product("u1", 10.0), product("u2", 20.0), product("gone", 5.0)])
    diff = compare(load_snapshot(snap), [product("u1", 12.5), product("u2", 20.0), product("new", 7.0)])
    assert [(c.url, c.delta, c.percent) for c in diff.changes] == [("u1", 2.5, 25.0)]
    assert [p.url for p in diff.added] == ["new"] and diff.removed == ["gone"]
    assert "Изменилось цен: 1" in format_report(diff, 3)


def test_excel_and_csv_export(tmp_path):
    products = [product("u1", 10.0, "Alpha"), product("u2", 30.0, "Beta")]
    snap = tmp_path / "s.json"
    save_snapshot(snap, [product("u1", 8.0)])
    diff = compare(load_snapshot(snap), products)
    wb = load_workbook(write_excel(products, diff, tmp_path / "out.xlsx", source="test"))
    assert wb.sheetnames == ["Каталог", "Сводка", "Изменения цен"]
    catalog = wb["Каталог"]
    assert catalog["A2"].value == "Alpha" and catalog["C2"].value == 10.0 and catalog["D2"].value == stars(3)
    assert catalog["F2"].hyperlink.target == "u1"
    assert wb["Сводка"]["B2"].value == 2
    assert wb["Изменения цен"]["B2"].value == 8.0 and wb["Изменения цен"]["C2"].value == 10.0
    csv_text = write_csv(products, tmp_path / "out.csv").read_text(encoding="utf-8-sig")
    assert csv_text.splitlines()[1] == "Alpha;C;10.00;3;1;u1"
