import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from multitool_transcriber.cli import _resolve_model, main
from multitool_transcriber.engine import Segment, Transcript, Word
from multitool_transcriber.models import ModelInfo


def model(name, language):
    return ModelInfo(name, Path("/models") / name, 1, language)


class ModelSelectionTests(unittest.TestCase):
    def test_defaults_to_russian(self):
        english = model("vosk-model-small-en-us-0.15", "en")
        russian = model("vosk-model-small-ru-0.22", "ru")
        with patch("multitool_transcriber.cli.discover_models", return_value=[english, russian]):
            path = _resolve_model(Namespace(model=None, model_dir=None, language=None))
        self.assertEqual(path, russian.path)

    def test_honours_explicit_language(self):
        english = model("vosk-model-small-en-us-0.15", "en")
        russian = model("vosk-model-small-ru-0.22", "ru")
        with patch("multitool_transcriber.cli.discover_models", return_value=[russian, english]):
            path = _resolve_model(Namespace(model=None, model_dir=None, language="en"))
        self.assertEqual(path, english.path)

    def test_missing_explicit_language_fails(self):
        russian = model("vosk-model-small-ru-0.22", "ru")
        with patch("multitool_transcriber.cli.discover_models", return_value=[russian]):
            with self.assertRaises(SystemExit):
                _resolve_model(Namespace(model=None, model_dir=None, language="en"))


class BatchOutputTests(unittest.TestCase):
    def test_duplicate_stems_get_distinct_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "in"
            output_dir = root / "out"
            first = source_dir / "a" / "lecture.wav"
            second = source_dir / "b" / "lecture.wav"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"")
            second.write_bytes(b"")
            transcript = Transcript(
                Path("lecture.wav"),
                "test-model",
                "ru",
                1.0,
                [Segment(0.0, 1.0, [Word("тест", 0.0, 1.0)])],
            )
            with (
                patch("multitool_transcriber.cli._resolve_model", return_value=Path("/models/ru")),
                patch("multitool_transcriber.cli.VoskEngine") as engine_class,
                patch(
                    "multitool_transcriber.cli.probe",
                    return_value=SimpleNamespace(duration=1.0),
                ),
            ):
                engine_class.return_value.transcribe.return_value = transcript
                code = main(
                    [
                        str(first),
                        str(second),
                        "-o",
                        str(output_dir),
                        "-f",
                        "txt",
                        "--quiet",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue((output_dir / "lecture.txt").exists())
            self.assertTrue((output_dir / "lecture (2).txt").exists())
            self.assertTrue((output_dir / "lecture.summary.txt").exists())
            self.assertTrue((output_dir / "lecture (2).summary.txt").exists())


if __name__ == "__main__":
    unittest.main()
