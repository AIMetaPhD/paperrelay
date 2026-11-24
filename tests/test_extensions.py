"""Tests for the plugin/preflight helpers added in v0.1.1."""

from __future__ import annotations

import unittest

from backend.extract import available_pdf_engines
from backend.metadata import openreview_id
from backend.preflight import _tool


class ExtensionTests(unittest.TestCase):
    def test_openreview_url_id(self):
        self.assertEqual(openreview_id("https://openreview.net/forum?id=nZeVKeeFYf9"), "nZeVKeeFYf9")
        self.assertEqual(openreview_id("https://openreview.net/forum?id=abc&noteId=x"), "abc")
        self.assertEqual(openreview_id("nZeVKeeFYf9"), "nZeVKeeFYf9")
        self.assertEqual(openreview_id("not a url"), "")

    def test_pdf_engines_include_pymupdf(self):
        engines = available_pdf_engines()
        self.assertIn("pymupdf", engines)

    def test_preflight_missing_tool(self):
        result = _tool("definitely-not-a-real-binary-xyz", "ffmpeg", "install it")
        self.assertEqual(result["status"], "fail")
        self.assertIn("install it", result["hint"])


if __name__ == "__main__":
    unittest.main()
