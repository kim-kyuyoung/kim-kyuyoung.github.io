#!/usr/bin/env python3
"""
data/publications.yaml -> index.html 의 publications 블록

index.html 은 사람이 직접 고치는 파일이다. 이 스크립트는 아래 두 표식 사이만
갈아끼우고 나머지는 한 글자도 건드리지 않는다.

    <!-- publications:start -->
    <!-- publications:end -->

사용:
    python scripts/inject_pubs.py
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PUBS = ROOT / "data" / "publications.yaml"
PAGE = ROOT / "index.html"

# 트랙별로 블록이 하나씩 있다. 분류는 data/overrides.yaml 의 professional_doi 로 정한다.
TRACKS = ("professional", "academic")

# 저자 목록에서 본인을 굵게 표시하기 위한 표기 변형
NAME_VARIANTS = {"kyuyoung kim", "kyu-young kim", "kyu young kim", "김규영"}

MAX_AUTHORS = 6  # 이보다 많으면 뒤를 et al. 로 줄인다


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def render_authors(authors: list[str]) -> str:
    if not authors:
        return ""

    shown = authors[:MAX_AUTHORS]
    parts = []
    for name in shown:
        if name.strip().lower() in NAME_VARIANTS:
            parts.append(f'<span class="me">{esc(name)}</span>')
        else:
            parts.append(esc(name))

    out = ", ".join(parts)
    if len(authors) > MAX_AUTHORS:
        out += " et al."
    return out


def render(pub: dict) -> str:
    title = esc(pub.get("title"))
    doi = pub.get("doi")
    if doi:
        title = f'<a href="https://doi.org/{esc(doi)}">{title}</a>'

    bits = []
    if pub.get("venue"):
        bits.append(f'<span class="venue">{esc(pub["venue"])}</span>')
    if pub.get("year"):
        bits.append(esc(pub["year"]))
    meta = ", ".join(bits)

    authors = render_authors(pub.get("authors") or [])

    return (
        "    <li>"
        f'<span class="what">{title}</span>'
        f'<span class="note">{authors}</span>'
        f'<span class="note">{meta}</span>'
        "</li>"
    )


def main() -> int:
    if not PUBS.exists():
        print(f"missing {PUBS}", file=sys.stderr)
        return 1

    doc = yaml.safe_load(PUBS.read_text(encoding="utf-8")) or {}
    pubs = doc.get("publications") or []
    pubs.sort(key=lambda p: (p.get("date") or "", p.get("year") or 0), reverse=True)

    page = PAGE.read_text(encoding="utf-8")
    original = page

    for track in TRACKS:
        start = f"<!-- publications:{track}:start -->"
        end = f"<!-- publications:{track}:end -->"

        if start not in page or end not in page:
            print(f"markers not found in {PAGE.name}: {start} / {end}", file=sys.stderr)
            return 1

        rows = [p for p in pubs if (p.get("track") or "academic") == track]
        block = "\n".join([start, *(render(p) for p in rows), end])

        page = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _: block,
            page,
            flags=re.DOTALL,
        )
        print(f"  {track:12} {len(rows)} publications")

    if page == original:
        print(f"  {PAGE.name} already up to date")
        return 0

    PAGE.write_text(page, encoding="utf-8")
    print(f"  updated {PAGE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
