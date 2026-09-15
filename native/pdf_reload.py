#!/usr/bin/env python3
"""Dependency-free native messaging host. Poll metadata, not browser tabs."""

import hashlib
import json
import os
from pathlib import Path
import queue
import struct
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

POLL_SECONDS = 0.25
SETTLE_SECONDS = 1.0
MAX_MESSAGE = 1024 * 1024


def path_from_url(url):
    parts = urlsplit(url)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        raise ValueError("Only local file URLs are supported")
    path = Path(unquote(parts.path, errors="strict"))
    if not path.is_absolute() or path.suffix.lower() != ".pdf" or "\0" in str(path):
        raise ValueError("Expected an absolute PDF path")
    return path


def signature(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def pdf_digest(path, expected):
    """Reject incomplete writes and replacements made during the read."""
    with path.open("rb") as file:
        if signature(os.fstat(file.fileno())) != expected:
            raise ValueError("PDF is still being written")
        if file.read(5) != b"%PDF-":
            raise ValueError("Waiting for a complete PDF")
        file.seek(max(0, expected[2] - 1024))
        if not file.read().rstrip().endswith(b"%%EOF"):
            raise ValueError("Waiting for the PDF end marker")
        file.seek(0)
        digest = hashlib.file_digest(file, "sha256").hexdigest()
        if signature(os.fstat(file.fileno())) != expected:
            raise ValueError("PDF changed during reading")
    if signature(path.stat()) != expected:
        raise ValueError("PDF was replaced during reading")
    return digest


class Watch:
    def __init__(self, url, now):
        self.url = url
        self.path = path_from_url(url)
        self.pending = None
        self.since = now
        self.digest = None
        self.checked = None
        self.error = None
        # Establish a baseline immediately so a compile right after enabling is seen.
        try:
            self.pending = signature(self.path.stat())
            self.digest = pdf_digest(self.path, self.pending)
            self.checked = self.pending
        except (OSError, ValueError):
            pass

    def tick(self, now):
        try:
            current = signature(self.path.stat())
            if current != self.pending:
                self.pending, self.since = current, now
                return None
            if current == self.checked or now - self.since < SETTLE_SECONDS:
                return None
            digest = pdf_digest(self.path, current)
            changed = digest != self.digest
            self.digest, self.checked, self.error = digest, current, None
            return {"type": "changed" if changed else "ready", "url": self.url}
        except (OSError, ValueError) as error:
            # Keep the old digest across deletion/recreation and failed compiles.
            message = str(error)
            if isinstance(error, OSError):
                self.pending, self.since = None, now
                message = error.strerror or "Cannot read PDF"
            if message != self.error:
                self.error = message
                return {"type": "error", "url": self.url, "message": message}
        return None


def read_exact(stream, length):
    data = bytearray()
    while len(data) < length:
        chunk = stream.read(length - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def read_messages(stream, inbox):
    try:
        while True:
            length = struct.unpack("=I", read_exact(stream, 4))[0]
            if length > MAX_MESSAGE:
                raise ValueError("Message too large")
            inbox.put(json.loads(read_exact(stream, length)))
    except (EOFError, ValueError, OSError):
        inbox.put(None)


def send(message):
    data = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(data)) + data)
    sys.stdout.buffer.flush()


def main():
    inbox = queue.Queue()
    threading.Thread(target=read_messages, args=(sys.stdin.buffer, inbox), daemon=True).start()
    watches = {}
    while True:
        try:
            message = inbox.get(timeout=POLL_SECONDS)
        except queue.Empty:
            message = {}
        if message is None:
            return
        if isinstance(message, dict) and message.get("type") == "watch":
            urls = message.get("urls")
            if not isinstance(urls, list) or len(urls) > 256 or not all(isinstance(u, str) for u in urls):
                continue
            watches = {url: watch for url, watch in watches.items() if url in urls}
            for url in urls:
                if url not in watches:
                    try:
                        watches[url] = Watch(url, time.monotonic())
                        send({"type": "ready", "url": url})
                    except (ValueError, OSError) as error:
                        send({"type": "error", "url": url, "message": str(error)})
        elif isinstance(message, dict) and message.get("type") == "status":
            send({"type": "status"})
        for watch in watches.values():
            event = watch.tick(time.monotonic())
            if event:
                send(event)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
