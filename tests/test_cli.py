import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from multitool_transcriber.cli import _resolve_model
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


if __name__ == "__main__":
    unittest.main()
