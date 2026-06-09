from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


LABELS = {
    "ISBN/ISSN": "isbn_issn",
    "价格": "price",
    "出版": "publication",
    "载体形态": "physical_description",
    "丛编": "series",
    "其他题名": "other_title",
    "中图分类号": "classno_abs",
    "责任者": "responsibility",
    "评分": "rating_text",
}


def clean_text(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def material_type_for(rec_ctrl_id: str | None) -> str:
    if rec_ctrl_id and rec_ctrl_id.startswith("1"):
        return "期刊"
    return "图书"


def normalize_book(item: dict[str, Any], category: Any, top_category_name: str, base_url: str) -> dict[str, Any]:
    rec_ctrl_id = item.get("recCtrlId") or ""
    terms = item.get("termList") or []
    return {
        "rec_ctrl_id": rec_ctrl_id,
        "category_code": category.code,
        "category_name": category.name,
        "top_category_code": category.top_code,
        "top_category_name": top_category_name,
        "title": item.get("title"),
        "authors": item.get("authors"),
        "isbn_issn": item.get("isn"),
        "publisher": item.get("publisher"),
        "publish_date": item.get("pubdateDate"),
        "classno_abs": item.get("classnoAbs"),
        "search_no": item.get("bookSearchNo"),
        "subject_terms": "; ".join(terms) if isinstance(terms, list) else item.get("subjectTerm"),
        "library_name": item.get("libraryName"),
        "holdings_count": item.get("guancangCount"),
        "available_count": item.get("kejieCount"),
        "rating": item.get("reGrade"),
        "comment_count": item.get("commentCount"),
        "material_type": material_type_for(rec_ctrl_id),
        "detail_url": urljoin(base_url + "/", f"bookInfo_{rec_ctrl_id}.html") if rec_ctrl_id else "",
        "raw_json": item,
    }


def parse_detail_fields(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    fields: dict[str, str] = {}
    for text in soup.get_text("\n").splitlines():
        line = clean_text(text)
        for label, key in LABELS.items():
            prefix = f"{label}:"
            prefix_cn = f"{label}："
            if line.startswith(prefix) or line.startswith(prefix_cn):
                fields[key] = clean_text(line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1])
    return fields


def parse_holdings(html: str, rec_ctrl_id: str, category_code: str, top_category_code: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    tbody = soup.find("tbody", id="guancanglist")
    if not tbody:
        return []

    rows: list[dict[str, str]] = []
    for tr in tbody.find_all("tr"):
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        cells = [cell for cell in cells if cell]
        links = tr.find_all("a", href=True)
        location_url = ""
        for link in links:
            if "position" in link.get("href", "") or "架位" in link.get_text("", strip=True):
                location_url = urljoin(base_url + "/", link["href"])
                break

        barcode = ""
        for cell in cells:
            if re.fullmatch(r"\d{6,}", cell):
                barcode = cell
                break
        if not barcode:
            for link in links:
                match = re.search(r"yujieTip\('([^']+)'", link.get("onclick", "") or link.get("href", ""))
                if match:
                    barcode = match.group(1)
                    break

        row = {
            "rec_ctrl_id": rec_ctrl_id,
            "category_code": category_code,
            "top_category_code": top_category_code,
            "department": cells[0] if cells else "",
            "barcode": barcode,
            "search_no": cells[2] if len(cells) > 2 else "",
            "register_no": cells[3] if len(cells) > 3 else "",
            "circulation_status": cells[-2] if len(cells) > 5 else "",
            "shelf_status": cells[-1] if len(cells) > 5 else "",
            "location_url": location_url,
            "raw_text": " | ".join(cells),
        }
        if any(row.values()):
            rows.append(row)
    return rows
