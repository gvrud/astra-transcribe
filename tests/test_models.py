import tempfile
import unittest
from pathlib import Path

from multitool_transcriber.models import discover_models, human_size, is_vosk_model


class ModelTests(unittest.TestCase):
    def test_model_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vosk-model-test"
            (root / "am").mkdir(parents=True)
            (root / "am" / "final.mdl").write_bytes(b"")
            (root / "conf").mkdir()
            (root / "conf" / "model.conf").write_text("", encoding="utf-8")
            (root / "graph").mkdir()
            self.assertTrue(is_vosk_model(root))
            self.assertFalse(is_vosk_model(root / "am"))
            infos = discover_models([Path(temporary)])
            self.assertTrue(any(info.name == "vosk-model-test" for info in infos))

    def test_human_size(self):
        self.assertEqual(human_size(47_000_000), "44.8 МБ")


if __name__ == "__main__":
    unittest.main()
