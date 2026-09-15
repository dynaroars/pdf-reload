import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("host", Path(__file__).parents[1] / "native/pdf_reload.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "a space # ü.pdf"
        self.path.write_bytes(b"%PDF-1.7\noriginal\n%%EOF\n")
        self.watch = host.Watch(self.path.as_uri(), 0)

    def settled(self, start=1):
        self.assertIsNone(self.watch.tick(start))
        return self.watch.tick(start + host.SETTLE_SECONDS + 0.1)

    def test_unchanged_and_touch_do_not_reload(self):
        self.assertIsNone(self.watch.tick(5))
        os.utime(self.path, ns=(10, 10))
        self.assertEqual(self.settled()["type"], "ready")
        self.assertIsNone(self.watch.tick(10))

    def test_partial_write_then_complete(self):
        self.path.write_bytes(b"%PDF-1.7\npartial")
        self.assertEqual(self.settled()["type"], "error")
        self.path.write_bytes(b"%PDF-1.7\nfinished\n%%EOF\n")
        self.assertEqual(self.settled(5)["type"], "changed")
        self.assertIsNone(self.watch.tick(10))

    def test_atomic_replacement(self):
        replacement = self.path.with_suffix(".tmp")
        replacement.write_bytes(b"%PDF-1.7\nreplaced\n%%EOF\n")
        replacement.replace(self.path)
        self.assertEqual(self.settled()["type"], "changed")

    def test_delete_recreate(self):
        self.path.unlink()
        self.assertEqual(self.watch.tick(1)["type"], "error")
        self.path.write_bytes(b"%PDF-1.7\nrebuilt\n%%EOF\n")
        self.assertEqual(self.settled(3)["type"], "changed")

    def test_write_bursts_reset_settle_timer(self):
        self.path.write_bytes(b"%PDF-1.7\nfirst\n%%EOF")
        self.assertIsNone(self.watch.tick(1))
        self.path.write_bytes(b"%PDF-1.7\nsecond\n%%EOF")
        self.assertIsNone(self.watch.tick(1.75))
        self.assertIsNone(self.watch.tick(2.1))
        self.assertEqual(self.watch.tick(3)["type"], "changed")

    def test_url_validation(self):
        self.assertEqual(host.path_from_url(self.path.as_uri()), self.path)
        for url in ["https://example.org/a.pdf", "file://remote/a.pdf", "file:///a.txt", "file:///a%00.pdf"]:
            with self.assertRaises(ValueError):
                host.path_from_url(url)


if __name__ == "__main__":
    unittest.main()
