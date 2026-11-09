import tempfile
import unittest
import zipfile
from pathlib import Path

from multitool_transcriber.models import DownloadError, import_model_zip, is_vosk_model


def write_model(archive, prefix=""):
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{prefix}am/final.mdl", b"")
        bundle.writestr(f"{prefix}conf/model.conf", b"")
        bundle.writestr(f"{prefix}graph/", b"")


class ModelImportTests(unittest.TestCase):
    def test_imports_zip_with_model_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "model.zip"
            write_model(archive, "vosk-model-test/")
            target = import_model_zip(archive, root / "models")
            self.assertTrue(is_vosk_model(target))
            self.assertEqual(target.name, "vosk-model-test")

    def test_imports_zip_with_files_at_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "my-ru-model.zip"
            write_model(archive)
            target = import_model_zip(archive, root / "models")
            self.assertTrue(is_vosk_model(target))
            self.assertEqual(target.name, "my-ru-model")

    def test_rejects_zip_without_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("readme.txt", "not a model")
            with self.assertRaises(DownloadError):
                import_model_zip(archive, root / "models")


if __name__ == "__main__":
    unittest.main()
