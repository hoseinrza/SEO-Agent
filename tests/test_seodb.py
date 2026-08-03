"""Tests for the keyword database rules.

Run: python3 -m unittest discover -s tests -v
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import seodb  # noqa: E402


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


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
