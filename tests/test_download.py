import http.server
import tempfile
import threading
import unittest
from pathlib import Path

from multitool_transcriber import models


PAYLOAD = bytes(range(256)) * 400


class TruncatedServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        self.first_request = True
        self.ranges = []
        super().__init__(("127.0.0.1", 0), Handler)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        request_range = self.headers.get("Range")
        if request_range:
            start = int(request_range.split("=", 1)[1].split("-", 1)[0])
            self.server.ranges.append(start)
            body = PAYLOAD[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            self.server.ranges.append(0)
            body = PAYLOAD
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not request_range and self.server.first_request:
            self.server.first_request = False
            self.wfile.write(PAYLOAD[:1000])
            self.wfile.flush()
            self.close_connection = True
            return
        self.wfile.write(body)


class DownloadTests(unittest.TestCase):
    def test_download_resumes_after_short_response(self):
        server = TruncatedServer()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        old_delay = models.DOWNLOAD_RETRY_DELAY
        models.DOWNLOAD_RETRY_DELAY = 0.01
        try:
            with tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / "model.bin"
                progress = []
                models._download_url(
                    f"http://127.0.0.1:{server.server_address[1]}/model.bin",
                    target,
                    lambda done, total: progress.append((done, total)),
                    None,
                )
                self.assertEqual(target.read_bytes(), PAYLOAD)
                self.assertEqual(server.ranges, [0, 1000])
                self.assertEqual(progress[-1], (len(PAYLOAD), len(PAYLOAD)))
        finally:
            models.DOWNLOAD_RETRY_DELAY = old_delay
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
