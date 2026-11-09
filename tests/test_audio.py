import tempfile
import unittest
import wave
from pathlib import Path

from multitool_transcriber.audio import iter_pcm16, probe


class AudioTests(unittest.TestCase):
    def test_wav_probe_and_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "silence.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(b"\x00\x00" * 16000)
            info = probe(path)
            self.assertAlmostEqual(info.duration, 1.0, places=1)
            self.assertEqual(info.sample_rate, 16000)
            data = b"".join(iter_pcm16(path))
            self.assertEqual(len(data), 32000)


if __name__ == "__main__":
    unittest.main()
