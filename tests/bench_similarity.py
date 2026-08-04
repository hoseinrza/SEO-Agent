#!/usr/bin/env python3
"""Benchmark for keyword-similarity detection: blocking index vs. pairwise scan.

Not a unit test (``unittest discover`` only collects ``test*.py``) — it exists to
put a number on the change, so the claim "the audit got faster" can be checked
instead of believed.

    python3 tests/bench_similarity.py                 # 500 / 1000 / 2000 / 5000
    python3 tests/bench_similarity.py --count 20000 --skip-legacy

The legacy implementation is kept here verbatim: it is what ``audit`` ran before
the blocking index, so the comparison is against real previous behaviour, and the
two are asserted to produce identical pairs at every size.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from difflib import SequenceMatcher

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import seodb  # noqa: E402

# --------------------------------------------------------------------------
# The implementation this change replaced
# --------------------------------------------------------------------------


def legacy_similarity(a: str, b: str) -> float:
    ta, tb = seodb.tokens(a), seodb.tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    flat_a = seodb.normalize(a).replace(" ", "")
    flat_b = seodb.normalize(b).replace(" ", "")
    chars = SequenceMatcher(None, flat_a, flat_b).ratio()
    return max(jaccard, chars if chars >= seodb.SPELLING_VARIANT_RATIO else 0.0)


def legacy_pairs(keywords: list, threshold: float) -> list:
    """The old O(n²) loop from ``audit``: every keyword against every other."""
    found = []
    for i, a in enumerate(keywords):
        for j in range(i + 1, len(keywords)):
            score = legacy_similarity(a, keywords[j])
            if score >= threshold:
                found.append((i, j, score))
    return found


# --------------------------------------------------------------------------
# Synthetic Persian keyword bank
# --------------------------------------------------------------------------

HEADS = [
    "یخچال", "فریزر", "ماشین لباسشویی", "ماشین ظرفشویی", "کولر گازی", "تلویزیون",
    "جاروبرقی", "مایکروویو", "پنکه", "اجاق گاز", "کیف لپتاپ", "کفش ورزشی",
    "دوربین مداربسته", "گوشی موبایل", "لپ تاپ", "هدفون بلوتوثی", "ساعت هوشمند",
    "تبلت", "پرینتر لیزری", "مانیتور گیمینگ",
]
MODIFIERS = [
    "خرید", "قیمت", "بهترین", "مقایسه", "فروش", "نمایندگی", "تعمیر", "نصب",
    "ارزان", "اقساطی", "دست دوم", "عمده",
]
BRANDS = [
    "سامسونگ", "ال جی", "بوش", "اسنوا", "دوو", "پاکشوما", "هیمالیا", "امرسان",
    "شارپ", "توشیبا", "جی پلاس", "زیرووات",
]
TAILS = ["", "۲۰۲۶", "در تهران", "با گارانتی", "اورجینال", "مدل جدید", "بدون واسطه"]
QUESTIONS = ["چگونه", "چطور", "بهترین مدل"]


def synthetic_keywords(count: int, seed: int = 20260804) -> list:
    """A keyword bank shaped like a real one: shared head terms, long tails,
    and a slice of spelling variants (ZWNJ / spacing) to keep the character
    branch of ``similarity`` in play."""
    rng = random.Random(seed)
    keywords, seen = [], set()
    while len(keywords) < count:
        head, brand = rng.choice(HEADS), rng.choice(BRANDS)
        parts = [rng.choice(MODIFIERS), head, brand, rng.choice(TAILS)]
        if rng.random() < 0.15:
            parts.insert(0, rng.choice(QUESTIONS))
        kw = " ".join(p for p in parts if p)
        if rng.random() < 0.05:  # a spelling variant of the same keyword
            kw = kw.replace(" ", "‌", 1)
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)
    return keywords


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return time.perf_counter() - start, result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, nargs="*", default=[500, 1000, 2000, 5000])
    parser.add_argument("--threshold", type=float, default=0.8, help="the audit default")
    parser.add_argument("--skip-legacy", action="store_true", help="only time the index")
    args = parser.parse_args(argv)

    print(f"threshold {args.threshold} · python {sys.version.split()[0]}\n")
    print("| keywords | legacy O(n²) | blocking index | speedup | pairs found |")
    print("| --- | --- | --- | --- | --- |")

    for count in sorted(args.count):
        keywords = synthetic_keywords(count)
        fast_time, fast = timed(
            lambda: list(seodb.KeywordIndex(keywords, args.threshold).pairs())
        )
        if args.skip_legacy:
            print(f"| {count} | — | {fast_time:.2f}s | — | {len(fast)} |")
            continue

        slow_time, slow = timed(lambda: legacy_pairs(keywords, args.threshold))
        if [(i, j) for i, j, _ in slow] != [(i, j) for i, j, _ in fast]:
            raise SystemExit(f"MISMATCH at {count} keywords — blocking dropped real matches")
        print(
            f"| {count} | {slow_time:.2f}s | {fast_time:.2f}s | "
            f"{slow_time / fast_time:.0f}× | {len(fast)} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
