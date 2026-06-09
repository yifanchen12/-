from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup


TOP_CATEGORY_RE = re.compile(r"^[A-Z]+")
INIT_RE = re.compile(r"init\('([^']+)',\s*1\)")


@dataclass(frozen=True)
class Category:
    code: str
    name: str
    parent_code: str
    top_code: str
    depth: int
    is_leaf: bool


def top_code_for(code: str) -> str:
    match = TOP_CATEGORY_RE.match(code)
    return match.group(0) if match else code[:1]


def parent_code_for(code: str, known_codes: set[str]) -> str:
    for length in range(len(code) - 1, 0, -1):
        parent = code[:length]
        if parent in known_codes:
            return parent
    return ""


def extract_categories(html: str) -> list[Category]:
    """Extract CLC category nodes from search-classify.html."""
    soup = BeautifulSoup(html, "lxml")
    raw: dict[str, str] = {}

    for tag in soup.find_all(attrs={"onclick": True}):
        onclick = tag.get("onclick", "")
        match = INIT_RE.search(onclick)
        if not match:
            continue
        code = match.group(1).strip()
        name = tag.get_text(" ", strip=True)
        if code and name:
            raw[code] = name

    known = set(raw)
    children: dict[str, int] = {code: 0 for code in raw}
    parents: dict[str, str] = {}
    for code in raw:
        parent = parent_code_for(code, known)
        parents[code] = parent
        if parent:
            children[parent] = children.get(parent, 0) + 1

    categories = [
        Category(
            code=code,
            name=raw[code],
            parent_code=parents[code],
            top_code=top_code_for(code),
            depth=len(code),
            is_leaf=children.get(code, 0) == 0,
        )
        for code in sorted(raw, key=lambda item: (top_code_for(item), len(item), item))
    ]
    return categories


def select_categories(categories: Iterable[Category], codes: list[str] | None, leaf_only: bool) -> list[Category]:
    items = list(categories)
    if codes:
        wanted = {code.upper() for code in codes}
        items = [item for item in items if item.code.upper() in wanted]
    if leaf_only:
        items = [item for item in items if item.is_leaf]
    return items

