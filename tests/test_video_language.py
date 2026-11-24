"""Chinese narration and subtitle regression checks (D2 Chinese video)."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from backend.video import _write_srt, scene_plan, voice_for

CJK = re.compile(r"[一-鿿]")


class ChineseVideoTests(unittest.TestCase):
    def test_voice_selection(self):
        settings = {"voice_en": "en-US-AriaNeural", "voice_zh": "zh-CN-YunxiNeural"}
        self.assertEqual(voice_for(settings, "zh"), "zh-CN-YunxiNeural")
        self.assertEqual(voice_for(settings, "en"), "en-US-AriaNeural")
        self.assertEqual(voice_for({}, "zh"), "zh-CN-XiaoxiaoNeural")

    def test_chinese_scene_plan_has_chinese_narration(self):
        version = {
            "title": "测试论文", "authors": ["张三", "李四"],
            "venue": "", "venue_source": "", "paper_url": "https://arxiv.org/abs/1234.5678",
            "code_url": "https://github.com/example/paper", "code_url_confirmed": 0,
            "abstract": "这是一段中文摘要。", "figures": [],
        }
        claims = [{"value": "28.4 BLEU", "source_page": 1, "source_quote": "测试原句", "status": "candidate"}]
        scenes = scene_plan(version, claims, lang="zh")
        self.assertTrue(all(CJK.search(s["narration"]) for s in scenes))
        joined = "\n".join(s["narration"] for s in scenes)
        self.assertIn("发表信息尚未确认", joined)
        self.assertNotIn("github.com", joined)

    def test_chinese_srt_round_trip(self):
        scenes = scene_plan({
            "title": "测试论文", "authors": ["张三"], "venue": "ICLR 2022", "venue_source": "OpenReview",
            "paper_url": "https://arxiv.org/abs/1234.5678", "abstract": "摘要。", "figures": [],
        }, [{"value": "3 倍", "source_page": 2, "source_quote": "原句", "status": "candidate"}], lang="zh")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "video.srt"
            _write_srt(scenes, [10.0] * len(scenes), out, lang="zh")
            text = out.read_text(encoding="utf-8")
        self.assertTrue(CJK.search(text))
        self.assertIn("-->", text)


if __name__ == "__main__":
    unittest.main()
