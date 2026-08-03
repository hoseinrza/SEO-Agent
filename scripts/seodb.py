#!/usr/bin/env python3
"""seodb — Keyword Database & SEO Reporting store for the SEO agent fleet.

CSV-backed, stdlib-only. Every project lives in one directory:

    projects/<slug>/
        project.json          # domain, industry, audience, country, language
        keywords.csv          # the keyword bank (one row per keyword)
        ranking-history.csv   # append-only position history
        clusters.csv          # keyword clusters
        pages.csv             # site pages (for orphan / cannibalization checks)
        competitors.csv       # competitor keyword rankings
        reports/              # generated markdown reports

Agents call this instead of hand-editing CSVs so the database rules
(no unregistered keyword, history is kept, cannibalization is detected)
are enforced by code rather than by good intentions.

Usage:
    python3 scripts/seodb.py --project projects/acme <command> ...
    python3 scripts/seodb.py --project projects/acme help-fields
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

KEYWORD_FIELDS = [
    "keyword",
    "main_topic",
    "search_intent",
    "search_volume",
    "keyword_difficulty",
    "cpc",
    "competition_level",
    "current_position",
    "target_position",
    "target_url",
    "content_type",
    "priority",
    "status",
    "last_checked",
    "cluster",
    "keyword_type",
    "notes",
]

HISTORY_FIELDS = ["date", "keyword", "position", "url", "source", "note"]
CLUSTER_FIELDS = [
    "cluster",
    "target_page",
    "search_intent",
    "content_structure",
    "related_keywords",
    "notes",
]
PAGE_FIELDS = [
    "url",
    "title",
    "page_type",
    "primary_keyword",
    "organic_traffic",
    "last_updated",
    "notes",
]
COMPETITOR_FIELDS = ["competitor", "keyword", "position", "url", "volume", "notes"]

SEARCH_INTENT = ["Informational", "Commercial", "Transactional", "Navigational"]
PRIORITY = ["High", "Medium", "Low"]
STATUS = ["New", "Planned", "Writing", "Published", "Ranking", "Improved"]
COMPETITION = ["Low", "Medium", "High"]
KEYWORD_TYPE = ["Primary", "Secondary", "Supporting", "Long Tail", "Question"]

ENUMS = {
    "search_intent": SEARCH_INTENT,
    "priority": PRIORITY,
    "status": STATUS,
    "competition_level": COMPETITION,
    "keyword_type": KEYWORD_TYPE,
}

FILES = {
    "keywords": ("keywords.csv", KEYWORD_FIELDS),
    "history": ("ranking-history.csv", HISTORY_FIELDS),
    "clusters": ("clusters.csv", CLUSTER_FIELDS),
    "pages": ("pages.csv", PAGE_FIELDS),
    "competitors": ("competitors.csv", COMPETITOR_FIELDS),
}

QUESTION_WORDS = {
    "how", "what", "why", "when", "where", "which", "who", "can", "does", "is",
    "چگونه", "چطور", "چیست", "چیه", "چرا", "کجا", "کدام", "چند", "آیا", "کی",
}

STOPWORDS = {
    "the", "a", "an", "of", "for", "in", "to", "and", "or", "best", "with",
    "و", "با", "در", "از", "به", "برای", "که", "را", "بر", "این", "آن",
}

# --------------------------------------------------------------------------
# Text normalisation (Persian/Arabic aware)
# --------------------------------------------------------------------------

_CHAR_MAP = {
    "ي": "ی",  # arabic yeh -> farsi yeh
    "ى": "ی",  # alef maksura -> farsi yeh
    "ك": "ک",  # arabic kaf -> keheh
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ة": "ه",
    "‌": " ",  # ZWNJ -> space
    "‏": "",
    "‎": "",
}
_DIACRITICS = re.compile(r"[ً-ْٰ]")
_PUNCT = re.compile(r"[^\w\s؀-ۿ]", re.UNICODE)
_DIGITS = {ord(c): str(i % 10) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩")}


def normalize(text: str) -> str:
    """Fold a keyword to a comparable form so duplicates cannot sneak in."""
    if not text:
        return ""
    text = text.strip().lower()
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    text = _DIACRITICS.sub("", text)
    text = text.translate(_DIGITS)
    text = _PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set:
    return {t for t in normalize(text).split() if t and t not in STOPWORDS}


#: Above this character-level ratio, two keywords are spelling variants of each
#: other rather than different keywords — "سایدبای‌ساید" vs "ساید بای ساید".
#: Genuinely different modifiers ("خرید ..." vs "قیمت ...") land around 0.85,
#: so the bar sits above them.
SPELLING_VARIANT_RATIO = 0.92


def similarity(a: str, b: str) -> float:
    """How much two keywords overlap, on a 0..1 scale.

    Token overlap (Jaccard) is the main signal, but Persian keywords are often
    written with different word spacing or a ZWNJ, which splits tokens that a
    reader would consider identical. So a very high character-level ratio on the
    space-stripped forms also counts as a match.
    """
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    flat_a, flat_b = normalize(a).replace(" ", ""), normalize(b).replace(" ", "")
    chars = SequenceMatcher(None, flat_a, flat_b).ratio()
    return max(jaccard, chars if chars >= SPELLING_VARIANT_RATIO else 0.0)


def is_question(kw: str) -> bool:
    parts = normalize(kw).split()
    return bool(parts) and bool(set(parts) & QUESTION_WORDS)


def classify_type(kw: str) -> str:
    """Default keyword_type when the researcher did not set one."""
    if is_question(kw):
        return "Question"
    if len(normalize(kw).split()) >= 4:
        return "Long Tail"
    return "Secondary"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


class UserError(Exception):
    """Bad input from the caller — reported without a traceback."""


def today() -> str:
    return date.today().isoformat()


def to_int(value, default=None):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_float(value, default=None):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_date(value):
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def path_for(root: str, kind: str) -> str:
    return os.path.join(root, FILES[kind][0])


def read_rows(root: str, kind: str) -> list:
    path = path_for(root, kind)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_rows(root: str, kind: str, rows: list) -> None:
    fields = FILES[kind][1]
    path = path_for(root, kind)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in fields})


def append_row(root: str, kind: str, row: dict) -> None:
    rows = read_rows(root, kind)
    rows.append(row)
    write_rows(root, kind, rows)


def load_project(root: str) -> dict:
    path = os.path.join(root, "project.json")
    if not os.path.exists(path):
        raise UserError(
            f"no project at {root!r} — run: seodb.py --project {root} init --domain <domain>"
        )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def match_enum(field: str, value: str) -> str:
    """Accept loose casing/spacing for enum fields, reject unknown values."""
    if value in (None, ""):
        return ""
    allowed = ENUMS[field]
    folded = normalize(value)
    for option in allowed:
        if normalize(option) == folded:
            return option
    raise UserError(f"{field}: «{value}» is not one of {', '.join(allowed)}")


def find_keyword(rows: list, keyword: str) -> dict | None:
    target = normalize(keyword)
    for row in rows:
        if normalize(row.get("keyword", "")) == target:
            return row
    return None


def position_of(row: dict):
    return to_int(row.get("current_position"), None)


def fmt_pos(value) -> str:
    pos = to_int(value, None)
    return str(pos) if pos else "—"


# --------------------------------------------------------------------------
# Commands: project + keywords
# --------------------------------------------------------------------------


def cmd_init(root: str, args) -> int:
    os.makedirs(os.path.join(root, "reports"), exist_ok=True)
    path = os.path.join(root, "project.json")
    project = {}
    if os.path.exists(path):
        project = load_project(root)
    project.update(
        {
            k: v
            for k, v in {
                "name": args.name,
                "domain": args.domain,
                "industry": args.industry,
                "target_audience": args.audience,
                "country": args.country,
                "language": args.language,
                "goals": args.goals,
            }.items()
            if v
        }
    )
    project.setdefault("name", args.domain or os.path.basename(root))
    project.setdefault("created", today())
    project["updated"] = today()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(project, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for kind in FILES:
        if not os.path.exists(path_for(root, kind)):
            write_rows(root, kind, [])
    print(f"project ready at {root} ({project.get('domain', 'no domain set')})")
    return 0


def cmd_kw_add(root: str, args) -> int:
    rows = read_rows(root, "keywords")
    if find_keyword(rows, args.keyword):
        raise UserError(
            f"«{args.keyword}» is already in the bank — use `kw update` instead of adding a duplicate"
        )

    near = [
        (row["keyword"], score)
        for row in rows
        if (score := similarity(args.keyword, row.get("keyword", ""))) >= args.similar_threshold
    ]
    if near and not args.force:
        listing = "\n".join(f"    {kw}  (similarity {score:.0%})" for kw, score in sorted(near, key=lambda x: -x[1])[:5])
        raise UserError(
            f"«{args.keyword}» looks like an existing keyword:\n{listing}\n"
            "  Map it to the same cluster/URL, or re-run with --force if it is genuinely distinct."
        )

    row = {
        "keyword": args.keyword.strip(),
        "main_topic": args.topic or "",
        "search_intent": match_enum("search_intent", args.intent),
        "search_volume": to_int(args.volume, "") or "",
        "keyword_difficulty": to_int(args.difficulty, "") or "",
        "cpc": args.cpc or "",
        "competition_level": match_enum("competition_level", args.competition),
        "current_position": to_int(args.position, "") or "",
        "target_position": to_int(args.target_position, "") or "",
        "target_url": args.url or "",
        "content_type": args.content_type or "",
        "priority": match_enum("priority", args.priority) or "Medium",
        "status": match_enum("status", args.status) or "New",
        "last_checked": args.date or (today() if args.position else ""),
        "cluster": args.cluster or "",
        "keyword_type": match_enum("keyword_type", args.type) or classify_type(args.keyword),
        "notes": args.notes or "",
    }
    rows.append(row)
    write_rows(root, "keywords", rows)
    if row["current_position"]:
        append_row(
            root,
            "history",
            {
                "date": row["last_checked"],
                "keyword": row["keyword"],
                "position": row["current_position"],
                "url": row["target_url"],
                "source": args.source or "manual",
                "note": "initial entry",
            },
        )
    print(f"added: {row['keyword']} [{row['keyword_type']} / {row['priority']} / {row['status']}]")
    if near:
        print(f"  note: {len(near)} similar keyword(s) already exist — check for cannibalization risk")
    return 0


def cmd_kw_update(root: str, args) -> int:
    rows = read_rows(root, "keywords")
    row = find_keyword(rows, args.keyword)
    if row is None:
        raise UserError(f"«{args.keyword}» is not in the bank — add it first")

    updates = {
        "main_topic": args.topic,
        "search_volume": args.volume,
        "keyword_difficulty": args.difficulty,
        "cpc": args.cpc,
        "target_position": args.target_position,
        "target_url": args.url,
        "content_type": args.content_type,
        "cluster": args.cluster,
        "notes": args.notes,
    }
    changed = []
    for field, value in updates.items():
        if value is not None:
            row[field] = value
            changed.append(field)
    for field, value in {
        "search_intent": args.intent,
        "priority": args.priority,
        "status": args.status,
        "competition_level": args.competition,
        "keyword_type": args.type,
    }.items():
        if value is not None:
            row[field] = match_enum(field, value)
            changed.append(field)

    if not changed:
        raise UserError("nothing to update — pass at least one field")
    write_rows(root, "keywords", rows)
    print(f"updated {row['keyword']}: {', '.join(changed)}")
    return 0


def cmd_kw_check(root: str, args) -> int:
    """Record a ranking observation: updates the row *and* appends history."""
    rows = read_rows(root, "keywords")
    row = find_keyword(rows, args.keyword)
    if row is None:
        raise UserError(
            f"«{args.keyword}» is not in the bank. Database rule: every keyword must be "
            "registered before it is tracked. Run `kw add` first."
        )

    when = args.date or today()
    old = position_of(row)
    new = to_int(args.position, None)
    url = args.url or row.get("target_url", "")

    history = read_rows(root, "history")
    best = min(
        [p for p in (to_int(h.get("position"), None) for h in history
                     if normalize(h.get("keyword", "")) == normalize(args.keyword)) if p],
        default=None,
    )

    row["current_position"] = new if new else ""
    row["last_checked"] = when
    # --url is the URL that actually ranked, which is not necessarily the URL we
    # are targeting — when they differ, that difference *is* the cannibalization
    # signal, so it is recorded in history and the target is left alone. Moving
    # the target is a strategy decision, taken explicitly with --retarget.
    if args.url and args.retarget:
        row["target_url"] = args.url

    if new:
        if row.get("status") in ("", "New", "Planned", "Writing", "Published"):
            row["status"] = "Ranking"
        if row.get("status") in ("Ranking", "Improved"):
            # "Improved" means "at or better than its best ever". Once the
            # keyword falls back below that, the status has to fall back too —
            # a report showing "Improved" for a keyword that just dropped is a
            # lie the roadmap would then act on.
            row["status"] = "Improved" if (best is not None and new <= best) else "Ranking"
    write_rows(root, "keywords", rows)

    append_row(
        root,
        "history",
        {
            "date": when,
            "keyword": row["keyword"],
            "position": new if new else "",
            "url": url,
            "source": args.source or "manual",
            "note": args.note or "",
        },
    )

    if old and new:
        delta = old - new
        arrow = "improved" if delta > 0 else ("dropped" if delta < 0 else "unchanged")
        print(f"{row['keyword']}: {old} -> {new} ({arrow} {abs(delta)})")
    elif new:
        print(f"{row['keyword']}: entered at position {new}")
    else:
        print(f"{row['keyword']}: no longer ranking (was {fmt_pos(old)})")
    return 0


def cmd_kw_search(root: str, args) -> int:
    """Rule: before proposing new content, check whether the keyword exists."""
    rows = read_rows(root, "keywords")
    scored = sorted(
        ((similarity(args.term, r.get("keyword", "")), r) for r in rows),
        key=lambda x: -x[0],
    )
    hits = [(s, r) for s, r in scored if s >= args.threshold]
    if not hits:
        print(f"no keyword similar to «{args.term}» (threshold {args.threshold:.0%}) — safe to add as new")
        return 0
    print(f"{len(hits)} existing keyword(s) similar to «{args.term}»:\n")
    print("| Similarity | Keyword | Cluster | Target URL | Status |")
    print("| --- | --- | --- | --- | --- |")
    for score, row in hits[: args.limit]:
        print(
            f"| {score:.0%} | {row['keyword']} | {row.get('cluster') or '—'} | "
            f"{row.get('target_url') or '—'} | {row.get('status') or '—'} |"
        )
    return 0


def filter_keywords(rows: list, args) -> list:
    out = rows
    if getattr(args, "status", None):
        out = [r for r in out if normalize(r.get("status")) == normalize(args.status)]
    if getattr(args, "priority", None):
        out = [r for r in out if normalize(r.get("priority")) == normalize(args.priority)]
    if getattr(args, "cluster", None):
        out = [r for r in out if normalize(r.get("cluster")) == normalize(args.cluster)]
    if getattr(args, "type", None):
        out = [r for r in out if normalize(r.get("keyword_type")) == normalize(args.type)]
    if getattr(args, "min_volume", None):
        out = [r for r in out if (to_int(r.get("search_volume"), 0) or 0) >= args.min_volume]
    return out


def sort_keywords(rows: list) -> list:
    order = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(
        rows,
        key=lambda r: (
            order.get(r.get("priority"), 3),
            -(to_int(r.get("search_volume"), 0) or 0),
            position_of(r) or 999,
        ),
    )


def cmd_kw_list(root: str, args) -> int:
    rows = sort_keywords(filter_keywords(read_rows(root, "keywords"), args))
    if not rows:
        print("no keywords match the filter")
        return 0
    print("| Keyword | Position | Volume | Difficulty | URL | Status | Priority |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(
            f"| {r['keyword']} | {fmt_pos(r.get('current_position'))} | "
            f"{r.get('search_volume') or '—'} | {r.get('keyword_difficulty') or '—'} | "
            f"{r.get('target_url') or '—'} | {r.get('status') or '—'} | {r.get('priority') or '—'} |"
        )
    print(f"\n{len(rows)} keyword(s)")
    return 0


# --------------------------------------------------------------------------
# Commands: clusters, pages, competitors
# --------------------------------------------------------------------------


def cmd_cluster_add(root: str, args) -> int:
    rows = read_rows(root, "clusters")
    existing = next((r for r in rows if normalize(r["cluster"]) == normalize(args.name)), None)
    payload = {
        "cluster": args.name.strip(),
        "target_page": args.page or "",
        "search_intent": match_enum("search_intent", args.intent),
        "content_structure": args.structure or "",
        "related_keywords": args.related or "",
        "notes": args.notes or "",
    }
    if existing:
        existing.update({k: v for k, v in payload.items() if v})
        action = "updated"
    else:
        rows.append(payload)
        action = "created"
    write_rows(root, "clusters", rows)
    print(f"cluster {action}: {payload['cluster']}")
    return 0


def cmd_cluster_list(root: str, args) -> int:
    clusters = read_rows(root, "clusters")
    keywords = read_rows(root, "keywords")
    if not clusters:
        print("no clusters defined")
        return 0
    for c in clusters:
        members = [k for k in keywords if normalize(k.get("cluster")) == normalize(c["cluster"])]
        print(f"\n## {c['cluster']}")
        print(f"- Target page: {c.get('target_page') or '— not set —'}")
        print(f"- Search intent: {c.get('search_intent') or '—'}")
        print(f"- Content structure: {c.get('content_structure') or '—'}")
        print(f"- Keywords: {len(members)}")
        for group in KEYWORD_TYPE:
            names = [m["keyword"] for m in members if m.get("keyword_type") == group]
            if names:
                print(f"  - {group}: {', '.join(names)}")
        orphans = [m["keyword"] for m in members if not m.get("keyword_type")]
        if orphans:
            print(f"  - Unclassified: {', '.join(orphans)}")
    return 0


def cmd_page_add(root: str, args) -> int:
    rows = read_rows(root, "pages")
    existing = next((r for r in rows if normalize(r["url"]) == normalize(args.url)), None)
    payload = {
        "url": args.url.strip(),
        "title": args.title or "",
        "page_type": args.page_type or "",
        "primary_keyword": args.primary_keyword or "",
        "organic_traffic": args.traffic or "",
        "last_updated": args.last_updated or today(),
        "notes": args.notes or "",
    }
    if existing:
        existing.update({k: v for k, v in payload.items() if v})
        action = "updated"
    else:
        rows.append(payload)
        action = "added"
    write_rows(root, "pages", rows)
    print(f"page {action}: {payload['url']}")
    return 0


def cmd_competitor_add(root: str, args) -> int:
    append_row(
        root,
        "competitors",
        {
            "competitor": args.competitor.strip(),
            "keyword": args.keyword.strip(),
            "position": to_int(args.position, "") or "",
            "url": args.url or "",
            "volume": to_int(args.volume, "") or "",
            "notes": args.notes or "",
        },
    )
    print(f"recorded: {args.competitor} ranks #{args.position or '?'} for «{args.keyword}»")
    return 0


# --------------------------------------------------------------------------
# Audit: the database management rules, enforced
# --------------------------------------------------------------------------


def audit(root: str, stale_days: int = 30, threshold: float = 0.8) -> dict:
    keywords = read_rows(root, "keywords")
    pages = read_rows(root, "pages")
    history = read_rows(root, "history")
    findings = {
        "duplicates": [],
        "near_duplicates": [],
        "cannibalization": [],
        "untargeted_pages": [],
        "keywords_without_url": [],
        "stale": [],
        "invalid": [],
        "unclustered": [],
    }

    seen = {}
    for row in keywords:
        key = normalize(row.get("keyword", ""))
        if not key:
            findings["invalid"].append("row with an empty keyword")
            continue
        if key in seen:
            findings["duplicates"].append(row["keyword"])
        seen[key] = row

    for field, allowed in ENUMS.items():
        for row in keywords:
            value = (row.get(field) or "").strip()
            if value and value not in allowed:
                findings["invalid"].append(f"{row['keyword']}: {field}=«{value}»")

    # Near-duplicates pointing at different URLs = planned cannibalization.
    items = list(keywords)
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            score = similarity(a.get("keyword", ""), b.get("keyword", ""))
            if score < threshold:
                continue
            url_a, url_b = (a.get("target_url") or "").strip(), (b.get("target_url") or "").strip()
            if url_a and url_b and normalize(url_a) != normalize(url_b):
                findings["cannibalization"].append(
                    {
                        "type": "planned",
                        "detail": f"{a['keyword']} -> {url_a}  vs  {b['keyword']} -> {url_b}",
                        "similarity": score,
                    }
                )
            else:
                findings["near_duplicates"].append(
                    {"a": a["keyword"], "b": b["keyword"], "similarity": score}
                )

    # Same keyword ranking with more than one URL = live cannibalization.
    by_keyword = {}
    for h in history:
        url = (h.get("url") or "").strip()
        if url:
            by_keyword.setdefault(normalize(h.get("keyword", "")), set()).add(url)
    for row in keywords:
        urls = by_keyword.get(normalize(row.get("keyword", "")), set())
        if len(urls) > 1:
            findings["cannibalization"].append(
                {
                    "type": "live",
                    "detail": f"{row['keyword']} has ranked with {len(urls)} URLs: {', '.join(sorted(urls))}",
                    "similarity": 1.0,
                }
            )

    targeted = {normalize(r.get("target_url")) for r in keywords if (r.get("target_url") or "").strip()}
    for page in pages:
        url = (page.get("url") or "").strip()
        if url and normalize(url) not in targeted and not (page.get("primary_keyword") or "").strip():
            findings["untargeted_pages"].append(url)

    for row in keywords:
        if not (row.get("target_url") or "").strip() and row.get("status") in ("Published", "Ranking", "Improved"):
            findings["keywords_without_url"].append(row["keyword"])
        if not (row.get("cluster") or "").strip():
            findings["unclustered"].append(row["keyword"])
        checked = parse_date(row.get("last_checked"))
        if row.get("status") in ("Published", "Ranking", "Improved"):
            if checked is None or (date.today() - checked).days > stale_days:
                findings["stale"].append(
                    f"{row['keyword']} (last checked: {row.get('last_checked') or 'never'})"
                )
    return findings


def cmd_audit(root: str, args) -> int:
    f = audit(root, stale_days=args.stale_days, threshold=args.threshold)
    problems = 0

    def section(title: str, items: list, render=lambda x: f"- {x}") -> None:
        nonlocal problems
        print(f"\n### {title} ({len(items)})")
        if not items:
            print("- clean")
            return
        problems += len(items)
        for item in items[: args.limit]:
            print(render(item))
        if len(items) > args.limit:
            print(f"- ... and {len(items) - args.limit} more")

    print("# Keyword Database Audit")
    section("Exact duplicates", f["duplicates"])
    section(
        "Cannibalization risks",
        f["cannibalization"],
        lambda x: f"- [{x['type']}] {x['detail']} ({x['similarity']:.0%} overlap)",
    )
    section(
        "Near-duplicate keywords (merge or differentiate)",
        f["near_duplicates"],
        lambda x: f"- {x['a']} ~ {x['b']} ({x['similarity']:.0%})",
    )
    section("Pages without a target keyword", f["untargeted_pages"])
    section("Live keywords without a target URL", f["keywords_without_url"])
    section("Keywords not assigned to a cluster", f["unclustered"])
    section(f"Stale rankings (> {args.stale_days} days)", f["stale"])
    section("Invalid field values", f["invalid"])

    print(f"\n**Total findings: {problems}**")
    return 1 if (problems and args.strict) else 0


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def observations(history: list, keyword: str) -> list:
    """All dated observations for a keyword, oldest first.

    Ties on the same date keep file order, so a same-day re-check wins.
    """
    key = normalize(keyword)
    rows = []
    for index, h in enumerate(history):
        if normalize(h.get("keyword", "")) != key:
            continue
        when = parse_date(h.get("date"))
        if when:
            rows.append((when, index, to_int(h.get("position"), None)))
    return sorted(rows, key=lambda o: (o[0], o[1]))


def baseline_position(history: list, keyword: str, cutoff: date):
    """The position to compare today's ranking against.

    Returns ``(position, had_prior_data)``. Normally the baseline is the last
    check on or before the cutoff. When a keyword was first tracked *inside* the
    window there is no such check, so the earliest in-window observation is used
    instead and ``had_prior_data`` is False — that keyword is newly tracked, not
    necessarily newly ranking.
    """
    obs = observations(history, keyword)
    if not obs:
        return None, False
    prior = [o for o in obs if o[0] <= cutoff]
    if prior:
        return prior[-1][2], True
    return obs[0][2], False


def ranking_changes(root: str, days: int) -> dict:
    keywords = read_rows(root, "keywords")
    history = read_rows(root, "history")
    cutoff = date.today() - timedelta(days=days)
    result = {
        "gained": [],
        "lost": [],
        "improved": [],
        "dropped": [],
        "unchanged": [],
        "newly_tracked": [],
    }
    for row in keywords:
        now = position_of(row)
        before, had_prior = baseline_position(history, row["keyword"], cutoff)
        entry = {
            "keyword": row["keyword"],
            "before": before,
            "now": now,
            "row": row,
            "new": not had_prior,
        }
        if not had_prior:
            result["newly_tracked"].append(entry)
        if now and not before:
            result["gained"].append(entry)
        elif before and not now:
            result["lost"].append(entry)
        elif before and now:
            if now < before:
                result["improved"].append(entry)
            elif now > before:
                result["dropped"].append(entry)
            else:
                result["unchanged"].append(entry)
    result["improved"].sort(key=lambda e: e["before"] - e["now"], reverse=True)
    result["dropped"].sort(key=lambda e: e["now"] - e["before"], reverse=True)
    return result


def opportunities(root: str) -> dict:
    """Data-driven buckets the roadmap is built from."""
    keywords = read_rows(root, "keywords")
    striking = [
        r for r in keywords
        if (p := position_of(r)) and 4 <= p <= 20
    ]
    striking.sort(key=lambda r: -(to_int(r.get("search_volume"), 0) or 0))
    quick = [r for r in striking if (to_int(r.get("keyword_difficulty"), 100) or 100) <= 40]
    unpublished = [r for r in keywords if r.get("status") in ("New", "Planned", "Writing")]
    unpublished = sort_keywords(unpublished)
    page2 = [r for r in keywords if (p := position_of(r)) and 11 <= p <= 20]
    missed_target = [
        r for r in keywords
        if (p := position_of(r)) and (t := to_int(r.get("target_position"), None)) and p > t
    ]
    return {
        "striking_distance": striking,
        "quick_wins": quick,
        "page_two": page2,
        "unpublished": unpublished,
        "below_target": missed_target,
    }


def md_table(headers: list, rows: list) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c) if str(c).strip() else "—" for c in row) + " |")
    return "\n".join(out)


def keyword_table(rows: list) -> str:
    return md_table(
        ["Keyword", "Position", "Volume", "Difficulty", "URL", "Status", "Priority"],
        [
            [
                r["keyword"],
                fmt_pos(r.get("current_position")),
                r.get("search_volume", ""),
                r.get("keyword_difficulty", ""),
                r.get("target_url", ""),
                r.get("status", ""),
                r.get("priority", ""),
            ]
            for r in rows
        ],
    )


def render_overview(root: str) -> str:
    p = load_project(root)
    keywords = read_rows(root, "keywords")
    ranking = [r for r in keywords if position_of(r)]
    top10 = [r for r in ranking if position_of(r) <= 10]
    top3 = [r for r in ranking if position_of(r) <= 3]
    avg = sum(position_of(r) for r in ranking) / len(ranking) if ranking else 0
    lines = [
        "### Website Overview",
        "",
        f"- **Domain:** {p.get('domain', '—')}",
        f"- **Industry:** {p.get('industry', '—')}",
        f"- **Target Audience:** {p.get('target_audience', '—')}",
        f"- **Country / Language:** {p.get('country', '—')} / {p.get('language', '—')}",
        f"- **Current SEO Status:** {len(keywords)} keywords tracked, {len(ranking)} ranking, "
        f"{len(top10)} in top 10, {len(top3)} in top 3"
        + (f", average position {avg:.1f}" if ranking else ""),
    ]
    return "\n".join(lines)


def render_changes(root: str, days: int) -> str:
    ch = ranking_changes(root, days)
    lines = [f"### Ranking Changes (last {days} days)", ""]
    lines.append(
        f"- Keywords gained: **{len(ch['gained'])}** | lost: **{len(ch['lost'])}** | "
        f"improved: **{len(ch['improved'])}** | dropped: **{len(ch['dropped'])}**"
    )
    if ch["newly_tracked"]:
        lines.append(
            f"- Newly tracked this period: **{len(ch['newly_tracked'])}** "
            "(no pre-window baseline — treat their movement as provisional)"
        )
    for title, key, arrow in [
        ("Keywords Gained", "gained", ""),
        ("Keywords Lost", "lost", ""),
        ("Position Improvements", "improved", "▲"),
        ("Position Drops", "dropped", "▼"),
    ]:
        entries = ch[key]
        lines += ["", f"**{title}** ({len(entries)})", ""]
        if not entries:
            lines.append("_none_")
            continue
        lines.append(
            md_table(
                ["Keyword", "Before", "Now", "Change", "URL"],
                [
                    [
                        e["keyword"],
                        fmt_pos(e["before"]),
                        fmt_pos(e["now"]),
                        f"{arrow} {abs(e['before'] - e['now'])}" if e["before"] and e["now"] else "—",
                        e["row"].get("target_url", ""),
                    ]
                    for e in entries[:20]
                ],
            )
        )
    return "\n".join(lines)


def render_traffic(root: str) -> str:
    pages = read_rows(root, "pages")
    keywords = read_rows(root, "keywords")
    ranked = sorted(
        [p for p in pages if to_int(p.get("organic_traffic"), None) is not None],
        key=lambda p: -(to_int(p.get("organic_traffic"), 0) or 0),
    )
    opp = opportunities(root)
    lines = ["### Traffic Analysis", ""]
    if ranked:
        lines += [
            "**Top Landing Pages**",
            "",
            md_table(
                ["URL", "Title", "Organic Traffic", "Primary Keyword"],
                [[p["url"], p.get("title", ""), p.get("organic_traffic", ""), p.get("primary_keyword", "")]
                 for p in ranked[:10]],
            ),
            "",
        ]
    else:
        lines += ["_No traffic data recorded yet (add pages with `page add --traffic`)._", ""]
    lines += ["**Traffic Opportunities** — striking-distance keywords (positions 4–20)", ""]
    lines.append(
        keyword_table(opp["striking_distance"][:15])
        if opp["striking_distance"]
        else "_none_"
    )
    stale_pages = [p for p in pages if (d := parse_date(p.get("last_updated"))) and (date.today() - d).days > 180]
    lines += ["", "**Declining / Ageing Pages** — not updated in 180+ days", ""]
    lines.append(
        md_table(["URL", "Last Updated", "Organic Traffic"],
                 [[p["url"], p.get("last_updated", ""), p.get("organic_traffic", "")] for p in stale_pages[:10]])
        if stale_pages
        else "_none_"
    )
    _ = keywords
    return "\n".join(lines)


def render_competitors(root: str) -> str:
    comp_rows = read_rows(root, "competitors")
    keywords = read_rows(root, "keywords")
    own = {normalize(k["keyword"]): k for k in keywords}
    lines = ["### Competitor Keyword Report", ""]
    if not comp_rows:
        return "\n".join(lines + ["_No competitor data recorded yet._"])
    by_competitor = {}
    for row in comp_rows:
        by_competitor.setdefault(row["competitor"], []).append(row)
    for name, rows in sorted(by_competitor.items()):
        shared, missing = [], []
        for row in rows:
            mine = own.get(normalize(row["keyword"]))
            (shared if mine else missing).append((row, mine))
        lines += [f"#### {name}", "", f"- Keywords ranking: **{len(rows)}**",
                  f"- Shared with us: **{len(shared)}** | Missing from our bank: **{len(missing)}**", ""]
        if shared:
            lines += [
                "**Shared Keywords**",
                "",
                md_table(
                    ["Keyword", "Their Position", "Our Position", "Gap", "Volume"],
                    [
                        [
                            row["keyword"],
                            fmt_pos(row.get("position")),
                            fmt_pos(mine.get("current_position")),
                            (lambda t, o: f"{o - t:+d}" if t and o else "—")(
                                to_int(row.get("position"), None), position_of(mine)
                            ),
                            row.get("volume", ""),
                        ]
                        for row, mine in shared[:15]
                    ],
                ),
                "",
            ]
        if missing:
            lines += [
                "**Missing Keywords (content opportunities)**",
                "",
                md_table(
                    ["Keyword", "Their Position", "Volume", "Their URL"],
                    [[row["keyword"], fmt_pos(row.get("position")), row.get("volume", ""), row.get("url", "")]
                     for row, _ in sorted(missing, key=lambda x: -(to_int(x[0].get("volume"), 0) or 0))[:15]],
                ),
                "",
            ]
    return "\n".join(lines)


def render_content(root: str) -> str:
    keywords = read_rows(root, "keywords")
    pages = read_rows(root, "pages")
    f = audit(root)
    winners = [r for r in keywords if (p := position_of(r)) and p <= 5]
    weak = [r for r in keywords if (p := position_of(r)) and p > 20]
    needs_update = [r for r in keywords if (p := position_of(r)) and 11 <= p <= 30
                    and r.get("status") in ("Published", "Ranking")]
    planned = [r for r in keywords if r.get("status") in ("New", "Planned", "Writing")]
    lines = [
        "### Content Performance Report",
        "",
        "**Winning pages** (keywords in top 5)",
        "",
        keyword_table(winners[:15]) if winners else "_none yet_",
        "",
        "**Weak pages** (published but ranking below 20)",
        "",
        keyword_table(weak[:15]) if weak else "_none_",
        "",
        "**Pages that need an update** (positions 11–30)",
        "",
        keyword_table(needs_update[:15]) if needs_update else "_none_",
        "",
        "**Content gap** (keywords in the bank without published content)",
        "",
        keyword_table(sort_keywords(planned)[:20]) if planned else "_none_",
        "",
        "**Pages without a target keyword** (assign one or de-index)",
        "",
        "\n".join(f"- {u}" for u in f["untargeted_pages"][:15]) if f["untargeted_pages"] else "_none_",
        "",
        f"_Site pages on record: {len(pages)}_",
    ]
    return "\n".join(lines)


def render_roadmap(root: str) -> str:
    opp = opportunities(root)
    f = audit(root)
    lines = ["## SEO Roadmap", "", "### Immediate Actions (0-7 Days)", ""]

    immediate = []
    for item in f["cannibalization"][:5]:
        immediate.append(
            f"Resolve cannibalization — {item['detail']}. Pick one canonical page, "
            "merge or de-optimize the other, and add an internal link from the weaker page."
        )
    for r in opp["quick_wins"][:5]:
        immediate.append(
            f"`{r['keyword']}` sits at #{fmt_pos(r.get('current_position'))} with difficulty "
            f"{r.get('keyword_difficulty') or '?'} and {r.get('search_volume') or '?'} searches — "
            f"refresh {r.get('target_url') or 'the target page'} (title, intro, internal links) for a fast win."
        )
    for url in f["untargeted_pages"][:3]:
        immediate.append(f"Assign a target keyword to {url} or remove it from the index.")
    if f["keywords_without_url"]:
        immediate.append(
            f"{len(f['keywords_without_url'])} live keyword(s) have no target URL — map them before the next check."
        )
    lines += [f"{i}. {t}" for i, t in enumerate(immediate, 1)] or ["_No urgent items — database is clean._"]

    lines += ["", "### Short Term (1-3 Months)", ""]
    short = []
    for r in opp["page_two"][:8]:
        short.append(
            f"Push `{r['keyword']}` from page 2 (#{fmt_pos(r.get('current_position'))}) into the top 10: "
            "expand depth, add supporting long-tail sections, build 2–3 internal links."
        )
    for r in opp["unpublished"][:8]:
        short.append(
            f"Publish content for `{r['keyword']}` ({r.get('priority') or 'Medium'} priority, "
            f"{r.get('search_volume') or '?'} volume, intent: {r.get('search_intent') or '—'}) "
            f"as {r.get('content_type') or 'a dedicated page'}."
        )
    lines += [f"{i}. {t}" for i, t in enumerate(short, 1)] or ["_Nothing queued._"]

    lines += ["", "### Long Term (3-12 Months)", ""]
    long_term = [
        "Build topical authority: complete every cluster with supporting and question keywords "
        "so each target page owns its topic map.",
        "Attack high-difficulty head terms only after the supporting cluster ranks — "
        "sequence them behind the long-tail wins above.",
        "Establish a link-building cadence for the money pages identified in the keyword bank.",
        "Re-audit technical health quarterly (Core Web Vitals, crawl budget, structured data).",
    ]
    if f["unclustered"]:
        long_term.insert(0, f"Cluster the {len(f['unclustered'])} keyword(s) that are still unassigned.")
    lines += [f"{i}. {t}" for i, t in enumerate(long_term, 1)]
    return "\n".join(lines)


def render_weekly(root: str, days: int) -> str:
    p = load_project(root)
    ch = ranking_changes(root, days)
    f = audit(root)
    opp = opportunities(root)
    lines = [
        f"# Weekly SEO Monitoring — {p.get('domain', '')}",
        f"_Week ending {today()} · comparison window: {days} days_",
        "",
        "## Summary",
        "",
        f"- New rankings: **{len(ch['gained'])}**",
        f"- Lost rankings: **{len(ch['lost'])}**",
        f"- Improvements: **{len(ch['improved'])}** | Drops: **{len(ch['dropped'])}**",
        f"- Database findings: **{sum(len(v) for v in f.values())}**",
        "",
        render_changes(root, days),
        "",
        "## New Keyword Opportunities",
        "",
        keyword_table(opp["quick_wins"][:10]) if opp["quick_wins"] else "_none this week_",
        "",
        "## Database Health",
        "",
        f"- Cannibalization risks: {len(f['cannibalization'])}",
        f"- Pages without target keyword: {len(f['untargeted_pages'])}",
        f"- Stale rankings: {len(f['stale'])}",
        f"- Unclustered keywords: {len(f['unclustered'])}",
        "",
        "## Next Actions",
        "",
    ]
    actions = []
    for e in ch["dropped"][:3]:
        actions.append(
            f"Investigate the drop on `{e['keyword']}` ({e['before']} → {e['now']}) — "
            "check SERP changes, cannibalization, and on-page relevance."
        )
    for r in opp["quick_wins"][:3]:
        actions.append(f"Optimize `{r['keyword']}` (#{fmt_pos(r.get('current_position'))}) for a quick win.")
    if f["cannibalization"]:
        actions.append(f"Resolve {len(f['cannibalization'])} cannibalization risk(s) — see audit output.")
    if f["stale"]:
        actions.append(f"Re-check {len(f['stale'])} keyword position(s) that have gone stale.")
    lines += [f"{i}. {t}" for i, t in enumerate(actions, 1)] or ["_Hold the current plan; nothing changed materially._"]
    return "\n".join(lines)


def render_full(root: str, days: int) -> str:
    p = load_project(root)
    keywords = sort_keywords(read_rows(root, "keywords"))
    parts = [
        f"# SEO Performance Report — {p.get('domain', '')}",
        f"_Generated {today()}_",
        "",
        render_overview(root),
        "",
        "### Keyword Report",
        "",
        keyword_table(keywords) if keywords else "_The keyword bank is empty._",
        "",
        render_changes(root, days),
        "",
        render_traffic(root),
        "",
        render_content(root),
        "",
        render_competitors(root),
        "",
        render_roadmap(root),
    ]
    return "\n".join(parts)


REPORTS = {
    "full": lambda root, args: render_full(root, args.days),
    "weekly": lambda root, args: render_weekly(root, args.days),
    "keywords": lambda root, args: keyword_table(sort_keywords(read_rows(root, "keywords"))),
    "changes": lambda root, args: render_changes(root, args.days),
    "traffic": lambda root, args: render_traffic(root),
    "content": lambda root, args: render_content(root),
    "competitors": lambda root, args: render_competitors(root),
    "roadmap": lambda root, args: render_roadmap(root),
    "overview": lambda root, args: render_overview(root),
}


def cmd_report(root: str, args) -> int:
    text = REPORTS[args.kind](root, args)
    if args.out:
        out = args.out
        if out == "auto":
            os.makedirs(os.path.join(root, "reports"), exist_ok=True)
            out = os.path.join(root, "reports", f"{today()}-{args.kind}.md")
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"written: {out}")
    else:
        print(text)
    return 0


def cmd_history(root: str, args) -> int:
    rows = [h for h in read_rows(root, "history")
            if not args.keyword or normalize(h.get("keyword", "")) == normalize(args.keyword)]
    rows.sort(key=lambda h: (h.get("keyword", ""), h.get("date", "")))
    if not rows:
        print("no history recorded")
        return 0
    print(md_table(
        ["Date", "Keyword", "Position", "URL", "Source", "Note"],
        [[h.get("date"), h.get("keyword"), fmt_pos(h.get("position")), h.get("url"), h.get("source"), h.get("note")]
         for h in rows[-args.limit:]],
    ))
    return 0


def cmd_help_fields(root: str, args) -> int:
    print("# Keyword bank schema\n")
    print("Columns of keywords.csv, in order:\n")
    for field in KEYWORD_FIELDS:
        allowed = ENUMS.get(field)
        print(f"- `{field}`" + (f" — one of: {', '.join(allowed)}" if allowed else ""))
    print("\nOther tables:\n")
    for kind, (name, fields) in FILES.items():
        if kind != "keywords":
            print(f"- `{name}`: {', '.join(fields)}")
    return 0


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seodb", description=__doc__.split("\n")[0])
    parser.add_argument(
        "--project",
        default=os.environ.get("SEO_PROJECT", "."),
        help="project directory (default: $SEO_PROJECT or the current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create or update a project")
    p.add_argument("--name")
    p.add_argument("--domain")
    p.add_argument("--industry")
    p.add_argument("--audience")
    p.add_argument("--country")
    p.add_argument("--language")
    p.add_argument("--goals")
    p.set_defaults(func=cmd_init)

    kw = sub.add_parser("kw", help="keyword bank operations").add_subparsers(dest="kwcmd", required=True)

    p = kw.add_parser("add", help="register a new keyword (blocks duplicates)")
    p.add_argument("keyword")
    p.add_argument("--topic")
    p.add_argument("--intent")
    p.add_argument("--volume")
    p.add_argument("--difficulty")
    p.add_argument("--cpc")
    p.add_argument("--competition")
    p.add_argument("--position")
    p.add_argument("--target-position")
    p.add_argument("--url")
    p.add_argument("--content-type")
    p.add_argument("--priority")
    p.add_argument("--status")
    p.add_argument("--cluster")
    p.add_argument("--type", help=f"one of: {', '.join(KEYWORD_TYPE)}")
    p.add_argument("--notes")
    p.add_argument("--date")
    p.add_argument("--source")
    p.add_argument("--force", action="store_true", help="add even if a similar keyword exists")
    p.add_argument("--similar-threshold", type=float, default=0.7)
    p.set_defaults(func=cmd_kw_add)

    p = kw.add_parser("update", help="edit fields of an existing keyword")
    p.add_argument("keyword")
    for flag in ["topic", "intent", "volume", "difficulty", "cpc", "competition",
                 "target-position", "url", "content-type", "priority", "status",
                 "cluster", "type", "notes"]:
        p.add_argument(f"--{flag}")
    p.set_defaults(func=cmd_kw_update)

    p = kw.add_parser("check", help="record a ranking observation (updates history)")
    p.add_argument("keyword")
    p.add_argument("--position", help="empty or 0 means 'not ranking'")
    p.add_argument("--url", help="the URL that actually ranked (recorded in history)")
    p.add_argument(
        "--retarget",
        action="store_true",
        help="also make --url the keyword's target_url (a strategy change)",
    )
    p.add_argument("--date")
    p.add_argument("--source")
    p.add_argument("--note")
    p.set_defaults(func=cmd_kw_check)

    p = kw.add_parser("search", help="check whether a similar keyword already exists")
    p.add_argument("term")
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_kw_search)

    p = kw.add_parser("list", help="list keywords as a markdown table")
    p.add_argument("--status")
    p.add_argument("--priority")
    p.add_argument("--cluster")
    p.add_argument("--type")
    p.add_argument("--min-volume", type=int)
    p.set_defaults(func=cmd_kw_list)

    cl = sub.add_parser("cluster", help="keyword clusters").add_subparsers(dest="clcmd", required=True)
    p = cl.add_parser("add", help="create or update a cluster")
    p.add_argument("name")
    p.add_argument("--page")
    p.add_argument("--intent")
    p.add_argument("--structure")
    p.add_argument("--related")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_cluster_add)
    p = cl.add_parser("list", help="show clusters with their members by type")
    p.set_defaults(func=cmd_cluster_list)

    pg = sub.add_parser("page", help="site pages").add_subparsers(dest="pgcmd", required=True)
    p = pg.add_parser("add", help="add or update a page")
    p.add_argument("url")
    p.add_argument("--title")
    p.add_argument("--page-type")
    p.add_argument("--primary-keyword")
    p.add_argument("--traffic")
    p.add_argument("--last-updated")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_page_add)

    cp = sub.add_parser("competitor", help="competitor rankings").add_subparsers(dest="cpcmd", required=True)
    p = cp.add_parser("add", help="record a competitor ranking")
    p.add_argument("competitor")
    p.add_argument("keyword")
    p.add_argument("--position")
    p.add_argument("--url")
    p.add_argument("--volume")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_competitor_add)

    p = sub.add_parser("audit", help="run the database management rules")
    p.add_argument("--stale-days", type=int, default=30)
    p.add_argument("--threshold", type=float, default=0.8)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--strict", action="store_true", help="exit 1 when findings exist")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("report", help="generate a markdown report")
    p.add_argument("kind", choices=sorted(REPORTS))
    p.add_argument("--days", type=int, default=7, help="comparison window for ranking changes")
    p.add_argument("--out", help="file path, or 'auto' for reports/<date>-<kind>.md")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("history", help="show the ranking history")
    p.add_argument("--keyword")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("help-fields", help="print the database schema")
    p.set_defaults(func=cmd_help_fields)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args.project, args)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
