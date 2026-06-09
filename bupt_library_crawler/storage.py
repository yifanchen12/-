from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
  code TEXT PRIMARY KEY,
  name TEXT,
  parent_code TEXT,
  top_code TEXT,
  depth INTEGER,
  is_leaf INTEGER
);

CREATE TABLE IF NOT EXISTS books (
  rec_ctrl_id TEXT PRIMARY KEY,
  category_code TEXT,
  category_name TEXT,
  top_category_code TEXT,
  top_category_name TEXT,
  title TEXT,
  authors TEXT,
  isbn_issn TEXT,
  publisher TEXT,
  publish_date TEXT,
  classno_abs TEXT,
  search_no TEXT,
  subject_terms TEXT,
  library_name TEXT,
  holdings_count INTEGER,
  available_count INTEGER,
  rating REAL,
  comment_count INTEGER,
  material_type TEXT,
  detail_url TEXT,
  raw_json TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS holdings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rec_ctrl_id TEXT,
  category_code TEXT,
  top_category_code TEXT,
  department TEXT,
  barcode TEXT,
  search_no TEXT,
  register_no TEXT,
  circulation_status TEXT,
  shelf_status TEXT,
  location_url TEXT,
  raw_text TEXT,
  UNIQUE(rec_ctrl_id, barcode, department, raw_text)
);

CREATE TABLE IF NOT EXISTS crawl_state (
  category_code TEXT PRIMARY KEY,
  last_page INTEGER NOT NULL DEFAULT 0,
  total_page INTEGER,
  total_records INTEGER,
  done INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(holdings)").fetchall()
        }
        if "register_no" not in columns:
            self.conn.execute("ALTER TABLE holdings ADD COLUMN register_no TEXT")

    def count_books(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM books").fetchone()
        return int(row["count"])

    def next_batch_number(self) -> int:
        row = self.conn.execute("SELECT value FROM metadata WHERE key = 'batch_number'").fetchone()
        current = int(row["value"]) if row else 0
        next_value = current + 1
        self.conn.execute(
            """
            INSERT INTO metadata(key, value)
            VALUES('batch_number', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(next_value),),
        )
        self.conn.commit()
        return next_value

    def clear_records(self) -> None:
        self.conn.execute("DELETE FROM holdings")
        self.conn.execute("DELETE FROM books")
        self.conn.commit()
        self.conn.execute("VACUUM")
        self.conn.commit()

    def upsert_categories(self, categories: Iterable[Any]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO categories(code, name, parent_code, top_code, depth, is_leaf)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            [
                (item.code, item.name, item.parent_code, item.top_code, item.depth, int(item.is_leaf))
                for item in categories
            ],
        )
        self.conn.commit()

    def get_top_category_name(self, top_code: str) -> str:
        row = self.conn.execute("SELECT name FROM categories WHERE code = ?", (top_code,)).fetchone()
        return row["name"] if row else top_code

    def get_state(self, category_code: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM crawl_state WHERE category_code = ?", (category_code,)).fetchone()

    def update_state(
        self,
        category_code: str,
        last_page: int,
        total_page: int | None,
        total_records: int | None,
        done: bool,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO crawl_state(category_code, last_page, total_page, total_records, done, updated_at)
            VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(category_code) DO UPDATE SET
              last_page = excluded.last_page,
              total_page = excluded.total_page,
              total_records = excluded.total_records,
              done = excluded.done,
              updated_at = CURRENT_TIMESTAMP
            """,
            (category_code, last_page, total_page, total_records, int(done)),
        )
        self.conn.commit()

    def upsert_book(self, book: dict[str, Any]) -> None:
        columns = [
            "rec_ctrl_id",
            "category_code",
            "category_name",
            "top_category_code",
            "top_category_name",
            "title",
            "authors",
            "isbn_issn",
            "publisher",
            "publish_date",
            "classno_abs",
            "search_no",
            "subject_terms",
            "library_name",
            "holdings_count",
            "available_count",
            "rating",
            "comment_count",
            "material_type",
            "detail_url",
            "raw_json",
        ]
        values = [book.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns[1:])
        self.conn.execute(
            f"""
            INSERT INTO books({", ".join(columns)})
            VALUES({placeholders})
            ON CONFLICT(rec_ctrl_id) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP
            """,
            values,
        )

    def replace_holdings(self, rec_ctrl_id: str, holdings: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM holdings WHERE rec_ctrl_id = ?", (rec_ctrl_id,))
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO holdings(
              rec_ctrl_id, category_code, top_category_code, department, barcode,
              search_no, register_no, circulation_status, shelf_status, location_url, raw_text
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.get("rec_ctrl_id"),
                    item.get("category_code"),
                    item.get("top_category_code"),
                    item.get("department"),
                    item.get("barcode"),
                    item.get("search_no"),
                    item.get("register_no"),
                    item.get("circulation_status"),
                    item.get("shelf_status"),
                    item.get("location_url"),
                    item.get("raw_text"),
                )
                for item in holdings
            ],
        )

    def save_record(self, book: dict[str, Any], holdings: list[dict[str, Any]]) -> None:
        if not isinstance(book.get("raw_json"), str):
            book["raw_json"] = json.dumps(book.get("raw_json", {}), ensure_ascii=False)
        self.upsert_book(book)
        self.replace_holdings(book["rec_ctrl_id"], holdings)
        self.conn.commit()
