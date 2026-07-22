#!/usr/bin/env python3
"""
ORCID(+ include_doi) -> data/publications.yaml

논문 목록의 기준은 ORCID 레코드다. OpenAlex 는 인용수·저널·저자 순서를 보강하는 용도로만 쓴다.

OpenAlex 의 author.orcid 필터는 쓰지 않는다. OpenAlex author A5074235764 가
여러 명의 "Kyuyoung / Kyu-Young Kim" 을 하나로 병합해 두고 거기에 이 ORCID 를
붙여 놓아서, 필터를 걸면 동명이인 논문 30여 편이 딸려 온다.

수집 대상 = ORCID works ∪ overrides.include_doi
  - ORCID 에 없는 본인 논문은 overrides.yaml 의 include_doi 에 DOI 를 적어 넣는다.
  - 동명이인/중복은 overrides.yaml 의 exclude_doi, exclude_id 로 뺀다.

사용:
    python scripts/fetch_pubs.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
import yaml

ORCID = "0000-0001-8011-3539"
MAILTO = os.environ.get("OPENALEX_MAILTO", "")  # polite pool. 넣으면 rate limit 여유

# OpenAlex 저자 목록에서 본인을 찾을 때 쓰는 표기 변형.
# OpenAlex 가 authorship 에 ORCID 를 붙여 주지 않는 논문이 많아 이름 매칭이 필요하다.
NAME_VARIANTS = {
    "kyuyoung kim",
    "kyu-young kim",
    "kyu young kim",
    "kim kyuyoung",
    "kim, kyuyoung",
    "김규영",
}

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "publications.yaml"
OVERRIDES = DATA / "overrides.yaml"

ORCID_API = f"https://pub.orcid.org/v3.0/{ORCID}/works"
API = "https://api.openalex.org/works"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = f"cv-site/1.0 (mailto:{MAILTO})" if MAILTO else "cv-site/1.0"


def norm_doi(value: str | None) -> str:
    """DOI 를 비교 가능한 형태로 통일한다."""
    if not value:
        return ""
    return (
        value.strip()
        .lower()
        .replace("https://doi.org/", "")
        .replace("http://dx.doi.org/", "")
        .replace("doi:", "")
    )


def fetch_orcid_works() -> tuple[set[str], list[dict]]:
    """ORCID 공개 API 에서 DOI 집합과, DOI 가 없는 항목의 요약 정보를 얻는다."""
    r = SESSION.get(ORCID_API, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()

    dois: set[str] = set()
    no_doi: list[dict] = []

    for group in r.json().get("group") or []:
        summary = (group.get("work-summary") or [{}])[0]
        doi = ""
        for eid in (group.get("external-ids") or {}).get("external-id") or []:
            if eid.get("external-id-type") == "doi":
                doi = norm_doi(eid.get("external-id-value"))
                break

        if doi:
            dois.add(doi)
            continue

        pub_date = summary.get("publication-date") or {}
        year = (pub_date.get("year") or {}).get("value")
        no_doi.append(
            {
                "title": ((summary.get("title") or {}).get("title") or {}).get("value"),
                "venue": (summary.get("journal-title") or {}).get("value"),
                "year": int(year) if year else None,
            }
        )

    return dois, no_doi


def fetch_by_dois(dois: list[str]) -> list[dict]:
    """OpenAlex 에서 DOI 로 works 를 가져온다. 필터 길이 제한 때문에 나눠 조회한다."""
    works: list[dict] = []
    batch = 40

    for i in range(0, len(dois), batch):
        chunk = dois[i : i + batch]
        params = {
            "filter": "doi:" + "|".join(chunk),
            "per-page": 200,
        }
        if MAILTO:
            params["mailto"] = MAILTO

        r = SESSION.get(API, params=params, timeout=30)
        r.raise_for_status()
        works.extend(r.json()["results"])
        time.sleep(0.2)

    return works


def normalize(w: dict) -> dict:
    """OpenAlex work 객체에서 CV에 필요한 필드만 뽑아 평평하게 만든다."""
    authorships = w.get("authorships") or []
    authors = [a["author"]["display_name"] for a in authorships if a.get("author")]

    # 본인이 몇 번째 저자인지 -> 사이트에서 bold 처리 및 '제1저자' 뱃지에 사용.
    # ORCID 가 붙어 있으면 그걸 쓰고, 없으면 이름 표기 변형으로 찾는다.
    my_position = None
    for idx, a in enumerate(authorships):
        orcid = (a.get("author") or {}).get("orcid") or ""
        if ORCID in orcid:
            my_position = idx + 1
            break
    if my_position is None:
        for idx, name in enumerate(authors):
            if name.strip().lower() in NAME_VARIANTS:
                my_position = idx + 1
                break

    loc = w.get("primary_location") or {}
    source = loc.get("source") or {}
    ids = w.get("ids") or {}

    return {
        "id": w["id"].rsplit("/", 1)[-1],
        "title": w.get("display_name"),
        "authors": authors,
        "author_position": my_position,
        "is_first_author": my_position == 1,
        "venue": source.get("display_name"),
        "year": w.get("publication_year"),
        "date": w.get("publication_date"),
        "type": w.get("type"),
        "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
        "pmid": (ids.get("pmid") or "").rsplit("/", 1)[-1] or None,
        "cited_by_count": w.get("cited_by_count", 0),
        "oa_url": (w.get("best_oa_location") or {}).get("landing_page_url"),
    }


def h_index(pubs: list[dict]) -> int:
    counts = sorted((p.get("cited_by_count") or 0 for p in pubs), reverse=True)
    return sum(1 for i, c in enumerate(counts, start=1) if c >= i)


def i10_index(pubs: list[dict]) -> int:
    return sum(1 for p in pubs if (p.get("cited_by_count") or 0) >= 10)


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    return yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) or {}


def apply_overrides(pubs: list[dict], ov: dict) -> list[dict]:
    exclude_doi = {norm_doi(d) for d in (ov.get("exclude_doi") or [])}
    exclude_id = set(ov.get("exclude_id") or [])
    patches = {norm_doi(k): v for k, v in (ov.get("patch_by_doi") or {}).items()}
    professional = {norm_doi(d) for d in (ov.get("professional_doi") or [])}

    kept = []
    for p in pubs:
        doi = norm_doi(p.get("doi"))
        if doi and doi in exclude_doi:
            continue
        if p["id"] in exclude_id:
            continue
        if doi in patches:
            p.update(patches[doi])
        p.setdefault("track", "professional" if doi in professional else "academic")
        kept.append(p)

    # OpenAlex가 색인하지 않는 것들(학회 초록, 구두발표, 프로시딩 등)을 수동 추가
    for manual in ov.get("manual") or []:
        manual.setdefault("id", "manual-" + str(abs(hash(manual.get("title", "")))))
        manual.setdefault("cited_by_count", 0)
        manual.setdefault("source", "manual")
        kept.append(manual)

    # 같은 DOI 로 두 건 이상이 잡히는 경우가 있다(OpenAlex 레코드 오류, 표지그림 등).
    # 인용수가 많은 쪽을 원 논문으로 보고 남긴다.
    by_doi: dict[str, dict] = {}
    deduped = []
    for p in kept:
        doi = norm_doi(p.get("doi"))
        if not doi:
            deduped.append(p)
            continue
        prev = by_doi.get(doi)
        if prev is None:
            by_doi[doi] = p
        elif (p.get("cited_by_count") or 0) > (prev.get("cited_by_count") or 0):
            by_doi[doi] = p
    deduped.extend(by_doi.values())

    deduped.sort(key=lambda p: (p.get("date") or "", p.get("year") or 0), reverse=True)
    return deduped


def main() -> int:
    ov = load_overrides()

    print(f"Fetching ORCID record {ORCID} ...")
    orcid_dois, orcid_no_doi = fetch_orcid_works()
    print(f"  {len(orcid_dois)} DOIs from ORCID ({len(orcid_no_doi)} entries without DOI)")

    include = {norm_doi(d) for d in (ov.get("include_doi") or [])}
    include.discard("")
    extra = include - orcid_dois
    if extra:
        print(f"  + {len(extra)} DOIs from overrides.include_doi")

    wanted = sorted(orcid_dois | include)
    print(f"Resolving {len(wanted)} DOIs on OpenAlex ...")
    raw = fetch_by_dois(wanted)

    found = {norm_doi(w.get("doi")) for w in raw}
    missing = [d for d in wanted if d not in found]
    if missing:
        print(f"  ! {len(missing)} DOIs not indexed by OpenAlex:")
        for d in missing:
            print(f"      {d}")

    pubs = [normalize(w) for w in raw]
    pubs = apply_overrides(pubs, ov)

    doc = {
        "orcid": ORCID,
        "generated_from": "orcid+openalex",
        "stats": {
            "count": len(pubs),
            "total_citations": sum(p.get("cited_by_count") or 0 for p in pubs),
            "h_index": h_index(pubs),
            "i10_index": i10_index(pubs),
            "first_author_count": sum(1 for p in pubs if p.get("is_first_author")),
        },
        "publications": pubs,
    }

    DATA.mkdir(exist_ok=True)
    OUT.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    s = doc["stats"]
    print(f"  wrote {OUT.relative_to(ROOT)}")
    print(f"  {s['count']} pubs / {s['total_citations']} citations / h={s['h_index']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
