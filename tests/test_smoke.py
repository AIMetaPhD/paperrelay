"""Minimal regression tests for the fact gate, extraction, publishing safety and site output.

Run from the repository root:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from backend import github_publish
from backend.facts import claim_is_meaningful, code_confirmed, scrub_unverified, venue_confirmed
from backend.generate import fact_check, facts_block
from backend.site import _bibtex
from backend.extract import _code_url


class FactPolicyTests(unittest.TestCase):
    def test_venue_needs_source(self):
        self.assertFalse(venue_confirmed({"venue": "ICLR 2022", "venue_source": ""}))
        self.assertTrue(venue_confirmed({"venue": "ICLR 2022", "venue_source": "OpenReview"}))

    def test_code_needs_confirmation(self):
        version = {"code_url": "https://github.com/a/b", "code_url_confirmed": 0}
        self.assertFalse(code_confirmed(version))
        version["code_url_confirmed"] = 1
        self.assertTrue(code_confirmed(version))

    def test_model_size_is_not_a_result(self):
        self.assertFalse(claim_is_meaningful({"value": "384 MB", "source_quote": "Each worker holds 384 MB."}))
        self.assertTrue(claim_is_meaningful({"value": "3x", "source_quote": "reduces memory by 3x versus baseline"}))
        self.assertTrue(claim_is_meaningful({"value": "28.4 BLEU", "source_quote": "reaches 28.4 BLEU"}))

    def test_scrub_removes_unconfirmed_venue_and_code(self):
        version = {"venue": "", "venue_source": "", "code_url": "https://github.com/a/b", "code_url_confirmed": 0}
        text = "Published at NeurIPS 2017. Code: https://github.com/a/b. Read it."
        cleaned = scrub_unverified(text, version)
        self.assertNotIn("NeurIPS", cleaned)
        self.assertNotIn("github.com", cleaned)

    def test_fact_check_flags_unconfirmed_venue_and_code(self):
        version = {"title": "T", "authors": [], "venue": "", "venue_source": "",
                   "code_url": "https://github.com/x/y", "code_url_confirmed": 0, "abstract": ""}
        issues = fact_check("Published at NeurIPS 2017. Code https://github.com/x/y. It uses 123456 tokens.", version, [])
        types = {issue["type"] for issue in issues}
        self.assertIn("venue_unverified", types)
        self.assertIn("code_url_unverified", types)
        self.assertIn("unknown_number", types)

    def test_facts_block_marks_candidate_claims(self):
        version = {"title": "T", "authors": ["A"], "venue": "", "venue_source": "", "abstract": "x"}
        block = facts_block(version, [{"value": "28.4 BLEU", "source_page": 3, "source_quote": "q", "status": "candidate"}])
        self.assertIn("[candidate] 28.4 BLEU", block)
        self.assertIn("UNCONFIRMED", block)


class ExtractionTests(unittest.TestCase):
    def test_release_phrase_is_accepted(self):
        self.assertEqual(_code_url("Code is available at https://github.com/example/paper"),
                         "https://github.com/example/paper")

    def test_bare_footnote_url_is_rejected(self):
        self.assertEqual(_code_url("We use the library in footnote 1. https://github.com/tensorflow/tensor2tensor"), "")

    def test_generic_dependency_is_rejected(self):
        self.assertEqual(_code_url("Implementation follows https://github.com/pytorch/pytorch"), "")


class SiteTests(unittest.TestCase):
    def test_bibtex_has_one_closing_brace(self):
        bib = _bibtex({"title": "T", "authors": ["A B"], "venue": "ICLR 2022",
                       "venue_source": "OpenReview", "year": "2021"})
        self.assertTrue(bib.rstrip().endswith("}"))
        self.assertFalse(bib.rstrip().endswith("}}"))
        self.assertIn("booktitle={ICLR 2022}", bib)


class PublishSafetyTests(unittest.TestCase):
    def test_unapproved_publish_is_blocked(self):
        result = github_publish.publish_site(Path("."), "owner/repo", approve=False)
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_missing_repository_is_never_created(self):
        calls: list[list[str]] = []

        def fake_run(args, cwd=None):
            calls.append(args)
            if args[:3] == ["gh", "repo", "view"]:
                return 1, "", "not found"
            return 0, "", ""

        with mock.patch.object(github_publish, "_run", side_effect=fake_run), \
                mock.patch.object(github_publish, "github_status", return_value={"ok": True, "account": "tester"}):
            result = github_publish.publish_site(Path("."), "owner/missing", approve=True)
        self.assertFalse(result["ok"])
        self.assertIn("never creates public repositories", result["error"])
        self.assertFalse(any(call[:3] == ["gh", "repo", "create"] for call in calls))

    def test_unverified_page_is_not_reported_live(self):
        def fake_run(args, cwd=None):
            return 0, "", ""

        class FakeResponse:
            status_code = 404
            text = ""

        with mock.patch.object(github_publish, "_run", side_effect=fake_run), \
                mock.patch.object(github_publish, "_enable_pages", return_value=(True, "")), \
                mock.patch.object(github_publish, "github_status", return_value={"ok": True, "account": "tester"}), \
                mock.patch.object(github_publish.requests, "get", return_value=FakeResponse()), \
                mock.patch.object(github_publish.time, "sleep", return_value=None):
            result = github_publish.publish_site(Path("."), "owner/repo", approve=True, title="T")
        self.assertTrue(result["ok"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["live"])


if __name__ == "__main__":
    unittest.main()
