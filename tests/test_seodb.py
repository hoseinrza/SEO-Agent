"""Tests for the keyword database rules.

Run: python3 -m unittest discover -s tests -v
"""

import contextlib
import glob
import io
import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import seodb  # noqa: E402
from bench_similarity import synthetic_keywords  # noqa: E402


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def cli_worker(root: str, argv: list, barrier=None) -> None:
    """Run one seodb command in a separate process, optionally in lockstep.

    Module level so it survives pickling under the 'spawn' start method.
    """
    if barrier is not None:
        barrier.wait()
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
        seodb.main(["--project", root, *argv])


class DBTestCase(unittest.TestCase):
    """Base class giving each test an isolated project directory."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="seodb-test-")
        self.cli("init", "--domain", "example.com", "--country", "IR", "--language", "fa")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *args):
        """Run a command through the real parser, letting UserError propagate.

        ``seodb.main`` deliberately swallows UserError and returns exit code 2,
        so the rule-enforcement tests dispatch one level below it. Command
        output is captured into ``self.output`` to keep test runs readable.
        """
        parsed = seodb.build_parser().parse_args(["--project", self.root, *args])
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                return parsed.func(self.root, parsed)
        finally:
            self.output = buffer.getvalue()

    def main(self, *args) -> int:
        """Run through seodb.main, which converts UserError into an exit code."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            return seodb.main(["--project", self.root, *args])

    def keywords(self):
        return seodb.read_rows(self.root, "keywords")

    def history(self):
        return seodb.read_rows(self.root, "history")


class TestNormalisation(unittest.TestCase):
    def test_persian_character_variants_fold_together(self):
        # Arabic yeh/kaf vs Persian yeh/keheh — the same word to a reader.
        self.assertEqual(seodb.normalize("كيف"), seodb.normalize("کیف"))

    def test_zwnj_and_spacing_fold_together(self):
        self.assertEqual(seodb.normalize("نیم‌فاصله"), seodb.normalize("نیم فاصله"))

    def test_digits_and_punctuation_are_folded(self):
        self.assertEqual(seodb.normalize("یخچال ۱۲!"), "یخچال 12")

    def test_case_and_whitespace(self):
        self.assertEqual(seodb.normalize("  Best   Laptop  "), "best laptop")


class TestSimilarity(unittest.TestCase):
    def test_identical_keywords(self):
        self.assertEqual(seodb.similarity("laptop bag", "laptop bag"), 1.0)

    def test_spelling_variant_counts_as_the_same_keyword(self):
        # Different word spacing is an orthographic variant, not a new keyword.
        score = seodb.similarity("خرید یخچال سایدبای‌ساید", "خرید یخچال ساید بای ساید")
        self.assertGreaterEqual(score, 0.9)

    def test_different_modifier_is_not_a_duplicate(self):
        # "buy X" and "price of X" are distinct intents and must stay separate.
        score = seodb.similarity("قیمت یخچال ساید بای ساید", "خرید یخچال ساید بای ساید")
        self.assertLess(score, 0.8)

    def test_unrelated_keywords(self):
        self.assertLess(seodb.similarity("laptop bag", "coffee machine"), 0.2)

    def test_empty_input(self):
        self.assertEqual(seodb.similarity("", "laptop"), 0.0)


class TestKeywordType(unittest.TestCase):
    def test_question_keyword_detected_in_persian(self):
        self.assertEqual(seodb.classify_type("چگونه یخچال بخریم"), "Question")

    def test_question_keyword_detected_in_english(self):
        self.assertEqual(seodb.classify_type("how to clean a fridge"), "Question")

    def test_long_tail_by_word_count(self):
        self.assertEqual(seodb.classify_type("یخچال ساید بای ساید سامسونگ"), "Long Tail")

    def test_short_keyword_defaults_to_secondary(self):
        self.assertEqual(seodb.classify_type("یخچال ساید"), "Secondary")


class TestRegistration(DBTestCase):
    def test_keyword_is_registered_with_defaults(self):
        self.cli("kw", "add", "laptop bag", "--intent", "Commercial", "--volume", "500")
        rows = self.keywords()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["keyword"], "laptop bag")
        self.assertEqual(rows[0]["search_intent"], "Commercial")
        self.assertEqual(rows[0]["priority"], "Medium")
        self.assertEqual(rows[0]["status"], "New")

    def test_exact_duplicate_is_rejected(self):
        self.cli("kw", "add", "laptop bag")
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "add", "Laptop  Bag")
        self.assertEqual(len(self.keywords()), 1)

    def test_spelling_variant_is_rejected(self):
        self.cli("kw", "add", "خرید یخچال ساید بای ساید")
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "add", "خرید یخچال سایدبای‌ساید")
        self.assertEqual(len(self.keywords()), 1)

    def test_force_allows_a_deliberate_near_duplicate(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "add", "laptop bag leather", "--force")
        self.assertEqual(len(self.keywords()), 2)

    def test_distinct_intent_is_not_blocked(self):
        self.cli("kw", "add", "خرید یخچال ساید بای ساید")
        self.cli("kw", "add", "قیمت یخچال ساید بای ساید")
        self.assertEqual(len(self.keywords()), 2)

    def test_invalid_enum_is_rejected(self):
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "add", "laptop bag", "--intent", "Shopping")

    def test_enum_accepts_loose_casing(self):
        self.cli("kw", "add", "laptop bag", "--intent", "transactional", "--priority", "HIGH")
        self.assertEqual(self.keywords()[0]["search_intent"], "Transactional")
        self.assertEqual(self.keywords()[0]["priority"], "High")


class TestRankingHistory(DBTestCase):
    def test_check_requires_a_registered_keyword(self):
        # Database rule: nothing is tracked before it is registered.
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "check", "unknown keyword", "--position", "5")

    def test_check_updates_row_and_appends_history(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "12", "--source", "gsc")
        self.assertEqual(self.keywords()[0]["current_position"], "12")
        self.assertEqual(self.keywords()[0]["status"], "Ranking")
        self.assertEqual(len(self.history()), 1)
        self.assertEqual(self.history()[0]["source"], "gsc")

    def test_history_is_append_only_across_checks(self):
        self.cli("kw", "add", "laptop bag")
        for pos in ("20", "15", "9"):
            self.cli("kw", "check", "laptop bag", "--position", pos)
        self.assertEqual([h["position"] for h in self.history()], ["20", "15", "9"])

    def test_beating_the_best_ever_position_marks_improved(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "15")
        self.cli("kw", "check", "laptop bag", "--position", "8")
        self.assertEqual(self.keywords()[0]["status"], "Improved")

    def test_falling_back_below_the_best_reverts_improved_to_ranking(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "15")
        self.cli("kw", "check", "laptop bag", "--position", "8")
        self.assertEqual(self.keywords()[0]["status"], "Improved")
        self.cli("kw", "check", "laptop bag", "--position", "19")
        self.assertEqual(self.keywords()[0]["status"], "Ranking")

    def test_holding_the_best_position_stays_improved(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "15")
        self.cli("kw", "check", "laptop bag", "--position", "8")
        self.cli("kw", "check", "laptop bag", "--position", "8")
        self.assertEqual(self.keywords()[0]["status"], "Improved")

    def test_ranking_url_does_not_overwrite_the_target_url(self):
        # A competing page appearing in the SERP is a cannibalization signal,
        # not a decision to retarget the keyword.
        self.cli("kw", "add", "laptop bag", "--url", "/bags")
        self.cli("kw", "check", "laptop bag", "--position", "9", "--url", "/blog/best-bags")
        self.assertEqual(self.keywords()[0]["target_url"], "/bags")
        self.assertEqual(self.history()[0]["url"], "/blog/best-bags")

    def test_retarget_moves_the_target_url_explicitly(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags")
        self.cli("kw", "check", "laptop bag", "--position", "9",
                 "--url", "/blog/best-bags", "--retarget")
        self.assertEqual(self.keywords()[0]["target_url"], "/blog/best-bags")

    def test_dropping_out_of_the_serp_is_recorded(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "8")
        self.cli("kw", "check", "laptop bag", "--position", "")
        self.assertEqual(self.keywords()[0]["current_position"], "")
        self.assertEqual(len(self.history()), 2)


class TestRankingChanges(DBTestCase):
    def test_improvement_against_a_pre_window_baseline(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "18", "--date", days_ago(30))
        self.cli("kw", "check", "laptop bag", "--position", "6", "--date", days_ago(1))
        changes = seodb.ranking_changes(self.root, days=7)
        self.assertEqual(len(changes["improved"]), 1)
        self.assertEqual(changes["improved"][0]["before"], 18)
        self.assertEqual(changes["improved"][0]["now"], 6)

    def test_drop_is_detected(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "5", "--date", days_ago(30))
        self.cli("kw", "check", "laptop bag", "--position", "22", "--date", days_ago(1))
        changes = seodb.ranking_changes(self.root, days=7)
        self.assertEqual(len(changes["dropped"]), 1)

    def test_keyword_entering_the_serp_counts_as_gained(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "", "--date", days_ago(30))
        self.cli("kw", "check", "laptop bag", "--position", "14", "--date", days_ago(1))
        changes = seodb.ranking_changes(self.root, days=7)
        self.assertEqual(len(changes["gained"]), 1)

    def test_keyword_leaving_the_serp_counts_as_lost(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "4", "--date", days_ago(30))
        self.cli("kw", "check", "laptop bag", "--position", "", "--date", days_ago(1))
        changes = seodb.ranking_changes(self.root, days=7)
        self.assertEqual(len(changes["lost"]), 1)

    def test_first_observation_inside_window_is_newly_tracked_not_gained(self):
        # No pre-window baseline exists, so the movement is provisional.
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "check", "laptop bag", "--position", "30", "--date", days_ago(5))
        self.cli("kw", "check", "laptop bag", "--position", "11", "--date", days_ago(1))
        changes = seodb.ranking_changes(self.root, days=7)
        self.assertEqual(len(changes["gained"]), 0)
        self.assertEqual(len(changes["newly_tracked"]), 1)
        self.assertEqual(len(changes["improved"]), 1)


class TestAudit(DBTestCase):
    def test_clean_database_has_no_findings(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        findings = seodb.audit(self.root)
        self.assertEqual(findings["cannibalization"], [])
        self.assertEqual(findings["duplicates"], [])
        self.assertEqual(findings["unclustered"], [])

    def test_live_cannibalization_when_one_keyword_ranks_with_two_urls(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("kw", "check", "laptop bag", "--position", "8", "--url", "/bags")
        self.cli("kw", "check", "laptop bag", "--position", "9", "--url", "/blog/best-bags")
        live = [c for c in seodb.audit(self.root)["cannibalization"] if c["type"] == "live"]
        self.assertEqual(len(live), 1)

    def test_planned_cannibalization_for_near_duplicates_on_different_urls(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("kw", "add", "laptop bags", "--url", "/other", "--cluster", "bags", "--force")
        planned = [c for c in seodb.audit(self.root)["cannibalization"] if c["type"] == "planned"]
        self.assertEqual(len(planned), 1)

    def test_near_duplicates_sharing_one_url_are_not_cannibalization(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("kw", "add", "laptop bags", "--url", "/bags", "--cluster", "bags", "--force")
        findings = seodb.audit(self.root)
        self.assertEqual(findings["cannibalization"], [])
        self.assertEqual(len(findings["near_duplicates"]), 1)

    def test_page_without_a_target_keyword_is_flagged(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("page", "add", "/orphan-page", "--title", "Orphan")
        self.assertEqual(seodb.audit(self.root)["untargeted_pages"], ["/orphan-page"])

    def test_page_with_a_targeting_keyword_is_not_flagged(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("page", "add", "/bags", "--title", "Bags")
        self.assertEqual(seodb.audit(self.root)["untargeted_pages"], [])

    def test_published_keyword_without_url_is_flagged(self):
        self.cli("kw", "add", "laptop bag", "--status", "Published", "--cluster", "bags")
        self.assertIn("laptop bag", seodb.audit(self.root)["keywords_without_url"])

    def test_stale_ranking_is_flagged(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("kw", "check", "laptop bag", "--position", "5", "--date", days_ago(90))
        self.assertEqual(len(seodb.audit(self.root, stale_days=30)["stale"]), 1)

    def test_recent_ranking_is_not_stale(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags")
        self.cli("kw", "check", "laptop bag", "--position", "5")
        self.assertEqual(seodb.audit(self.root, stale_days=30)["stale"], [])

    def test_unclustered_keyword_is_flagged(self):
        self.cli("kw", "add", "laptop bag", "--url", "/bags")
        self.assertIn("laptop bag", seodb.audit(self.root)["unclustered"])


class TestReports(DBTestCase):
    def setUp(self):
        super().setUp()
        self.cli("kw", "add", "laptop bag", "--url", "/bags", "--cluster", "bags",
                 "--volume", "5000", "--difficulty", "30", "--priority", "High",
                 "--intent", "Transactional")
        self.cli("kw", "check", "laptop bag", "--position", "12", "--date", days_ago(20))
        self.cli("kw", "check", "laptop bag", "--position", "6", "--date", days_ago(1))

    def test_every_report_kind_renders(self):
        class Args:
            days = 7

        for kind, render in seodb.REPORTS.items():
            with self.subTest(report=kind):
                output = render(self.root, Args())
                self.assertIsInstance(output, str)
                self.assertTrue(output.strip(), f"{kind} report was empty")

    def test_full_report_contains_the_required_sections(self):
        class Args:
            days = 7

        report = seodb.REPORTS["full"](self.root, Args())
        for section in [
            "Website Overview",
            "Keyword Report",
            "Ranking Changes",
            "Traffic Analysis",
            "Content Performance Report",
            "Competitor Keyword Report",
            "SEO Roadmap",
        ]:
            self.assertIn(section, report)

    def test_roadmap_has_all_three_horizons(self):
        class Args:
            days = 7

        roadmap = seodb.REPORTS["roadmap"](self.root, Args())
        self.assertIn("Immediate Actions (0-7 Days)", roadmap)
        self.assertIn("Short Term (1-3 Months)", roadmap)
        self.assertIn("Long Term (3-12 Months)", roadmap)

    def test_keyword_table_reports_the_current_position(self):
        table = seodb.keyword_table(seodb.read_rows(self.root, "keywords"))
        self.assertIn("laptop bag", table)
        self.assertIn("| 6 |", table)

    def test_striking_distance_opportunity_is_detected(self):
        opp = seodb.opportunities(self.root)
        self.assertEqual(len(opp["striking_distance"]), 1)
        self.assertEqual(len(opp["quick_wins"]), 1)


class TestClustersAndPages(DBTestCase):
    def test_cluster_is_created_then_updated_in_place(self):
        self.cli("cluster", "add", "bags", "--page", "/bags", "--intent", "Commercial")
        self.cli("cluster", "add", "bags", "--structure", "H1 + comparison table")
        clusters = seodb.read_rows(self.root, "clusters")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["target_page"], "/bags")
        self.assertEqual(clusters[0]["content_structure"], "H1 + comparison table")

    def test_page_is_updated_in_place(self):
        self.cli("page", "add", "/bags", "--title", "Bags")
        self.cli("page", "add", "/bags", "--traffic", "1200")
        pages = seodb.read_rows(self.root, "pages")
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["organic_traffic"], "1200")
        self.assertEqual(pages[0]["title"], "Bags")

    def test_competitor_ranking_is_recorded(self):
        self.cli("competitor", "add", "rival.com", "laptop bag", "--position", "2", "--volume", "5000")
        rows = seodb.read_rows(self.root, "competitors")
        self.assertEqual(rows[0]["competitor"], "rival.com")
        self.assertEqual(rows[0]["position"], "2")


class TestCLIWrapper(DBTestCase):
    def test_main_reports_user_errors_as_exit_code_2(self):
        self.cli("kw", "add", "laptop bag")
        code = self.main("kw", "add", "laptop bag")
        self.assertEqual(code, 2)

    def test_main_returns_0_on_success(self):
        code = self.main("kw", "add", "laptop bag")
        self.assertEqual(code, 0)

    def test_audit_strict_exits_nonzero_when_findings_exist(self):
        self.cli("kw", "add", "laptop bag")  # no cluster -> a finding
        code = self.main("audit", "--strict")
        self.assertEqual(code, 1)


class TestConcurrentWrites(DBTestCase):
    """The manager runs subagents in parallel — parallel writes must not lose rows."""

    KEYWORDS = ["laptop", "coffee", "bicycle", "guitar", "notebook", "camera", "printer", "umbrella"]

    def run_workers(self, workers, timeout=60):
        for worker in workers:
            worker.start()
        try:
            for worker in workers:
                worker.join(timeout=timeout)
                self.assertFalse(worker.is_alive(), "a parallel seodb command never finished")
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()

    def test_parallel_kw_add_keeps_every_row(self):
        barrier = multiprocessing.Barrier(len(self.KEYWORDS))
        self.run_workers(
            [
                multiprocessing.Process(target=cli_worker, args=(self.root, ["kw", "add", kw], barrier))
                for kw in self.KEYWORDS
            ]
        )
        stored = [row["keyword"] for row in self.keywords()]
        self.assertEqual(sorted(stored), sorted(self.KEYWORDS))
        self.assertEqual(len(stored), len(set(stored)), "a keyword was written twice")

    def test_parallel_writes_to_different_tables_do_not_block_each_other(self):
        # The lock is per table, so holding the keyword bank must leave the page
        # table writable — otherwise parallel subagents would serialise on
        # everything, and one long keyword run would stall all the others.
        with seodb.locked(self.root, "keywords"):
            self.run_workers(
                [multiprocessing.Process(target=cli_worker, args=(self.root, ["page", "add", "/bags"]))],
                timeout=20,
            )
        self.assertEqual(len(seodb.read_rows(self.root, "pages")), 1)


class TestAtomicWrite(DBTestCase):
    def test_write_leaves_no_temporary_files_behind(self):
        self.cli("kw", "add", "laptop bag")
        self.assertEqual(glob.glob(os.path.join(self.root, ".seodb-*")), [])

    def raw(self) -> str:
        with open(os.path.join(self.root, "keywords.csv"), encoding="utf-8") as fh:
            return fh.read()

    def test_a_failed_write_leaves_the_previous_table_intact(self):
        self.cli("kw", "add", "laptop bag")
        before = self.raw()

        rows = self.keywords() + [{"keyword": "coffee machine"}]
        with mock.patch.object(seodb, "escape_cell", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                seodb.write_rows(self.root, "keywords", rows)

        self.assertEqual(self.raw(), before)
        self.assertEqual(glob.glob(os.path.join(self.root, ".seodb-*")), [])


class TestCSVInjection(DBTestCase):
    """Values a spreadsheet would execute are quoted on disk, never in the data."""

    def raw(self, name="keywords.csv") -> str:
        with open(os.path.join(self.root, name), encoding="utf-8") as fh:
            return fh.read()

    def test_formula_keyword_is_quoted_on_disk_but_clean_when_read(self):
        self.cli("kw", "add", "=1+1")
        self.assertIn("'=1+1", self.raw())
        self.assertEqual(self.keywords()[0]["keyword"], "=1+1")

    def test_every_risky_prefix_is_neutralised(self):
        for value in ("=cmd()", "+1", "-1", "@SUM(A1)"):
            with self.subTest(value=value):
                self.assertEqual(seodb.escape_cell(value), "'" + value)
                self.assertEqual(seodb.unescape_cell("'" + value), value)

    def test_formula_note_is_quoted(self):
        self.cli("kw", "add", "laptop bag", "--notes", "=HYPERLINK(\"http://evil\",\"click\")")
        self.assertIn("'=HYPERLINK", self.raw())
        self.assertEqual(self.keywords()[0]["notes"], '=HYPERLINK("http://evil","click")')

    def test_ordinary_values_are_untouched(self):
        self.cli("kw", "add", "laptop bag", "--notes", "checked in GSC")
        self.assertNotIn("'", self.raw())

    def test_a_value_that_really_starts_with_a_quote_round_trips(self):
        self.assertEqual(seodb.unescape_cell(seodb.escape_cell("'=1+1")), "'=1+1")
        self.assertEqual(seodb.unescape_cell(seodb.escape_cell("'quoted'")), "'quoted'")

    def test_quoting_does_not_leak_into_matching_or_reporting(self):
        self.cli("kw", "add", "=1+1", "--url", "/calc")
        self.cli("kw", "check", "=1+1", "--position", "7")
        self.assertEqual(self.keywords()[0]["current_position"], "7")
        self.assertEqual(self.history()[0]["keyword"], "=1+1")
        self.assertIn("| =1+1 |", seodb.keyword_table(self.keywords()))

    def test_history_and_competitor_tables_are_escaped_too(self):
        self.cli("competitor", "add", "rival.com", "laptop bag", "--notes", "@evil")
        self.assertIn("'@evil", self.raw("competitors.csv"))
        self.assertEqual(seodb.read_rows(self.root, "competitors")[0]["notes"], "@evil")


class TestKeywordIndex(unittest.TestCase):
    """Blocking must only skip comparisons that could not have matched."""

    CORPUS = [
        "خرید یخچال ساید بای ساید",
        "خرید یخچال سایدبای‌ساید",
        "قیمت یخچال ساید بای ساید",
        "یخچال فریزر دوقلو",
        "بهترین یخچال ساید بای ساید",
        "یخچال ساید بای ساید سامسونگ",
        "laptop bag",
        "laptop bags",
        "leather laptop bag",
        "coffee machine",
        "best coffee machine",
        "چگونه یخچال بخریم",
        "نیم‌فاصله",
        "نیم فاصله",
        "کيف لپتاپ",
        "کیف لپ تاپ",
    ]

    def brute_force(self, keywords, threshold):
        return [
            (i, j, seodb.similarity(a, b))
            for i, a in enumerate(keywords)
            for j, b in enumerate(keywords)
            if i < j and seodb.similarity(a, b) >= threshold
        ]

    def test_pairs_match_the_exhaustive_scan(self):
        for threshold in (0.0, 0.3, 0.5, 0.7, 0.8, 0.9):
            with self.subTest(threshold=threshold):
                index = seodb.KeywordIndex(self.CORPUS, threshold)
                self.assertEqual(list(index.pairs()), self.brute_force(self.CORPUS, threshold))

    def test_matches_find_the_same_keywords_as_an_exhaustive_scan(self):
        for threshold in (0.5, 0.7, 0.8):
            index = seodb.KeywordIndex(self.CORPUS, threshold)
            for term in self.CORPUS + ["خرید یخچال", "laptop", "قهوه ساز"]:
                with self.subTest(threshold=threshold, term=term):
                    expected = [
                        (i, seodb.similarity(term, kw))
                        for i, kw in enumerate(self.CORPUS)
                        if seodb.similarity(term, kw) >= threshold
                    ]
                    self.assertEqual(index.matches(term), expected)

    def test_pairs_match_the_exhaustive_scan_on_a_generated_bank(self):
        # The hand-written corpus above is small enough to reason about; this one
        # is 300 generated Persian keywords with shared head terms and a slice of
        # ZWNJ spelling variants — the shape blocking is most likely to get wrong.
        keywords = synthetic_keywords(300)
        for threshold in (0.7, 0.8):
            with self.subTest(threshold=threshold):
                index = seodb.KeywordIndex(keywords, threshold)
                self.assertEqual(list(index.pairs()), self.brute_force(keywords, threshold))

    def test_spelling_variants_are_still_found_across_a_large_bank(self):
        # A common head term in every keyword is exactly the case blocking has to
        # survive: the shared token is too common to be useful, so the n-gram
        # bucket has to carry the match.
        corpus = [f"یخچال مدل {n}" for n in range(300)] + ["کیف لپتاپ", "کیف لپ تاپ"]
        index = seodb.KeywordIndex(corpus, 0.8)
        pairs = [(corpus[i], corpus[j]) for i, j, _ in index.pairs()]
        self.assertIn(("کیف لپتاپ", "کیف لپ تاپ"), pairs)

    def test_empty_bank_is_handled(self):
        self.assertEqual(list(seodb.KeywordIndex([], 0.8).pairs()), [])
        self.assertEqual(seodb.KeywordIndex([], 0.8).matches("laptop"), [])


class TestUpdate(DBTestCase):
    def test_update_changes_fields(self):
        self.cli("kw", "add", "laptop bag")
        self.cli("kw", "update", "laptop bag", "--status", "Published", "--url", "/bags")
        row = self.keywords()[0]
        self.assertEqual(row["status"], "Published")
        self.assertEqual(row["target_url"], "/bags")

    def test_update_requires_an_existing_keyword(self):
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "update", "missing", "--status", "Published")

    def test_update_without_fields_is_rejected(self):
        self.cli("kw", "add", "laptop bag")
        with self.assertRaises(seodb.UserError):
            self.cli("kw", "update", "laptop bag")


if __name__ == "__main__":
    unittest.main()
