from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tqdm import tqdm

from .categories import Category, extract_categories, select_categories, top_code_for
from .client import OpacClient
from .exporter import export_excel
from .parser import normalize_book, parse_detail_fields, parse_holdings
from .storage import Store


BASE_URL = "http://opac.bupt.edu.cn:8080"
REFERER_CLASSIFY = f"{BASE_URL}/search-classify.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl BUPT Library OPAC holdings and export Excel files.")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--db", type=Path, default=Path("data/bupt_library.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("output/bupt_library_holdings.xlsx"))
    parser.add_argument("--delay", type=float, default=1.2, help="Delay between HTTP requests in seconds.")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--codes", nargs="*", help="Limit to specific CLC category codes, for example B821 TP311.")
    parser.add_argument("--include-parent-categories", action="store_true", help="Also crawl non-leaf category nodes.")
    parser.add_argument("--max-pages", type=int, default=1, help="Safety limit per category. Use --full for all pages.")
    parser.add_argument("--max-books", type=int, default=0, help="Stop after this many books. 0 means no explicit cap.")
    parser.add_argument("--full", action="store_true", help="Crawl all pages for selected categories.")
    parser.add_argument("--resume", action="store_true", help="Resume from the SQLite crawl_state table.")
    parser.add_argument("--export-only", action="store_true", help="Skip crawling and export the existing SQLite database.")
    parser.add_argument("--log-level", default="INFO")
    return parser


def crawl(args: argparse.Namespace) -> None:
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    client = OpacClient(base_url=args.base_url, delay=args.delay)
    store = Store(args.db)

    if args.export_only:
        export_excel(args.db, args.output)
        return

    classify_html = client.get_text("search-classify.html", referer=f"{args.base_url}/index.html")
    categories = extract_categories(classify_html)
    store.upsert_categories(categories)
    selected = select_categories(categories, args.codes, leaf_only=not args.include_parent_categories)
    if not selected and args.codes:
        selected = [
            Category(
                code=code.upper(),
                name=code.upper(),
                parent_code="",
                top_code=top_code_for(code.upper()),
                depth=len(code),
                is_leaf=True,
            )
            for code in args.codes
        ]
    if not selected:
        raise SystemExit("No categories selected. Check --codes or the OPAC category page.")

    total_books = 0
    for category in tqdm(selected, desc="Categories"):
        state = store.get_state(category.code) if args.resume else None
        if state and state["done"]:
            continue

        start_page = (state["last_page"] + 1) if state else 1
        top_name = store.get_top_category_name(category.top_code)
        page_no = start_page
        total_page = None

        while True:
            payload = {
                "classnoAbs": category.code,
                "pageNo": page_no,
                "pageSize": args.page_size,
                "order": "-1",
            }
            data = client.post_json("search-classify.json", payload, referer=REFERER_CLASSIFY)
            if data.get("result", {}).get("code") != 0:
                raise RuntimeError(f"OPAC returned an error for {category.code} page {page_no}: {data}")

            total_page = int(data.get("totalPage") or 0)
            total_records = int(data.get("total") or 0)
            records = data.get("data") or []

            for item in tqdm(records, desc=f"{category.code} p{page_no}", leave=False):
                rec_ctrl_id = item.get("recCtrlId")
                if not rec_ctrl_id:
                    continue
                book = normalize_book(item, category, top_name, args.base_url)
                try:
                    info = client.post_json("search_info.json", {"sid": rec_ctrl_id}, referer=REFERER_CLASSIFY)
                    if info.get("result", {}).get("code") == 0 and isinstance(info.get("data"), dict):
                        book.update(normalize_book(info["data"], category, top_name, args.base_url))
                except Exception as exc:  # noqa: BLE001 - keep long crawl moving
                    logging.warning("failed to fetch search_info for %s: %s", rec_ctrl_id, exc)

                detail_html = ""
                try:
                    detail_html = client.get_text(f"bookInfo_{rec_ctrl_id}.html", referer=REFERER_CLASSIFY)
                    detail_fields = parse_detail_fields(detail_html)
                    if detail_fields.get("classno_abs"):
                        book["classno_abs"] = detail_fields["classno_abs"]
                except Exception as exc:  # noqa: BLE001 - keep long crawl moving
                    logging.warning("failed to fetch detail page for %s: %s", rec_ctrl_id, exc)

                holdings = parse_holdings(detail_html, rec_ctrl_id, category.code, category.top_code, args.base_url) if detail_html else []
                store.save_record(book, holdings)
                total_books += 1
                if args.max_books and total_books >= args.max_books:
                    store.update_state(category.code, page_no, total_page, total_records, done=False)
                    export_excel(args.db, args.output)
                    return

            done = bool(total_page and page_no >= total_page)
            store.update_state(category.code, page_no, total_page, total_records, done=done)

            if done:
                break
            if not args.full and page_no >= args.max_pages:
                break
            page_no += 1

    export_excel(args.db, args.output)
    store.close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    crawl(args)


if __name__ == "__main__":
    main()
