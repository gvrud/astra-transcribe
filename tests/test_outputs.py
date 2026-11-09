import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from multitool_transcriber.engine import Segment, Transcript, Word, _segment_from_json
from multitool_transcriber.outputs import (
    build_cues,
    capitalize_sentences,
    format_srt_time,
    render_json,
    render_srt,
    render_txt,
    unique_base_name,
    write_outputs,
)


def sample_transcript():
    first = [Word("привет", 0.0, 0.4), Word("мир", 0.5, 0.9)]
    second = [Word("это", 1.2, 1.4), Word("тест", 1.5, 1.9)]
    return Transcript(
        source=Path("audio.mp3"),
        model_name="test-model",
        language="ru",
        duration=2.0,
        segments=[Segment(0.0, 0.9, first), Segment(1.2, 1.9, second)],
    )


class OutputTests(unittest.TestCase):
    def test_capitalize_sentences(self):
        self.assertEqual(capitalize_sentences("привет. как дела?"), "Привет. Как дела?")

    def test_srt_time(self):
        self.assertEqual(format_srt_time(3661.234), "01:01:01,234")

    def test_cues_split_on_pause(self):
        cues = build_cues(sample_transcript().segments, max_gap=0.2)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].text, "привет мир")
        self.assertEqual(cues[1].text, "это тест")

    def test_render_txt(self):
        text = render_txt(sample_transcript())
        self.assertTrue(text.startswith("Привет мир"))
        self.assertIn("Это тест", text)

    def test_render_srt(self):
        srt = render_srt(sample_transcript(), max_gap=0.2)
        lines = srt.splitlines()
        self.assertEqual(lines[0], "1")
        self.assertEqual(lines[1], "00:00:00,000 --> 00:00:00,900")
        self.assertIn("Привет мир", srt)

    def test_render_json(self):
        payload = json.loads(render_json(sample_transcript()))
        self.assertEqual(payload["segments"][0]["words"][0]["word"], "привет")
        self.assertEqual(payload["duration"], 2.0)

    def test_write_outputs_docx(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_outputs(sample_transcript(), temporary, ["txt", "docx"])
            self.assertTrue(Path(paths["txt"]).exists())
            self.assertTrue(Path(paths["docx"]).exists())
            document = Document(paths["docx"])
            self.assertTrue(any("Привет мир" in item.text for item in document.paragraphs))

    def test_duplicate_stems_get_unique_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            used: set[str] = set()
            first_base = unique_base_name("lecture", used)
            second_base = unique_base_name("lecture", used)
            first = write_outputs(sample_transcript(), temporary, ["txt"], base_name=first_base)
            second = write_outputs(sample_transcript(), temporary, ["txt"], base_name=second_base)
            self.assertEqual(Path(first["txt"]).name, "lecture.txt")
            self.assertEqual(Path(second["txt"]).name, "lecture (2).txt")
            self.assertTrue(Path(first["txt"]).exists())
            self.assertTrue(Path(second["txt"]).exists())

    def test_comma_decimal_json(self):
        raw = '{"result":[{"conf":1,000000,"start":0,120000,"end":0,540000,"word":"родион"}]}'
        segment = _segment_from_json(raw)
        self.assertIsNotNone(segment)
        self.assertEqual(segment.words[0].text, "родион")
        self.assertAlmostEqual(segment.start, 0.12)
        self.assertAlmostEqual(segment.end, 0.54)


if __name__ == "__main__":
    unittest.main()
