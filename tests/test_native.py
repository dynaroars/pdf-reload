import importlib.util
import io
import os
import queue
import struct
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
        self.assertEqual(host.path_from_url("file:///tmp/%FF.pdf"), Path(os.fsdecode(b"/tmp/\xff.pdf")))

    def test_initial_failure_is_reported(self):
        self.path.write_bytes(b"%PDF-1.7\npartial")
        watch = host.Watch(self.path.as_uri(), 0)
        self.assertEqual(watch.status()["type"], "error")
        missing = host.Watch((Path(self.temp.name) / "missing.pdf").as_uri(), 0)
        self.assertEqual(missing.status()["type"], "error")

    def test_new_tab_learns_existing_error(self):
        url = self.path.as_uri()
        watches, events = host.update({}, [url], 0)
        self.assertEqual([e["type"] for e in events], ["ready"])
        self.path.unlink()
        self.assertEqual(watches[url].tick(1)["type"], "error")
        # A second tab watching the same URL resends the same list.
        watches, events = host.update(watches, [url], 2)
        self.assertEqual([e["type"] for e in events], ["error"])
        watches, events = host.update(watches, ["file:///a.txt"], 3)
        self.assertEqual((list(watches), events[0]["type"]), ([], "error"))

    def test_unchanged_incomplete_pdf_is_not_reread(self):
        self.path.write_bytes(b"%PDF-1.7\npartial")
        self.assertEqual(self.settled()["type"], "error")
        with mock.patch.object(host, "pdf_digest") as digest:
            self.assertIsNone(self.watch.tick(10))
        digest.assert_not_called()


class MessageTests(unittest.TestCase):
    def test_bad_json_is_skipped(self):
        frames = b"".join(struct.pack("=I", len(d)) + d for d in [b"{bad", b'{"type": "status"}'])
        inbox = queue.Queue()
        host.read_messages(io.BytesIO(frames), inbox)
        self.assertEqual([inbox.get_nowait(), inbox.get_nowait()], [{"type": "status"}, None])


class InstallTests(unittest.TestCase):
    def test_helper_uses_installing_python(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            subprocess.run([sys.executable, str(Path(__file__).parents[1] / "native/install.py"),
                            "--manifest-dir", str(temp / "manifests"), "--install-dir", str(temp / "helper")],
                           check=True, stdout=subprocess.DEVNULL)
            first_line = (temp / "helper/pdf_reload.py").read_bytes().split(b"\n", 1)[0]
            self.assertEqual(first_line, b"#!" + os.fsencode(os.path.abspath(sys._base_executable)))
            # Reinstalling over our own installation must succeed.
            subprocess.run([sys.executable, str(Path(__file__).parents[1] / "native/install.py"),
                            "--manifest-dir", str(temp / "manifests"), "--install-dir", str(temp / "helper")],
                           check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
