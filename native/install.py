#!/usr/bin/env python3
"""Install the helper for a normal, non-containerized Linux Firefox."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

HOST_SOURCE = Path(__file__).with_name("pdf_reload.py").read_bytes()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manifest-dir", type=Path,
                    default=Path.home() / ".mozilla/native-messaging-hosts")
parser.add_argument("--install-dir", type=Path,
                    default=Path.home() / ".local/share/local-pdf-reload")
args = parser.parse_args()
if sys.version_info < (3, 11):
    parser.error("Python 3.11 or newer is required")
host = args.install_dir.resolve() / "pdf_reload.py"
manifest = {
    "name": "local_pdf_reload",
    "description": "Watch local PDFs for Firefox",
    "path": str(host),
    "type": "stdio",
    "allowed_extensions": ["pdf-reload@local"],
}
target = args.manifest_dir / "local_pdf_reload.json"
contents = json.dumps(manifest, indent=2) + "\n"
if target.exists() and target.read_text() != contents:
    # Migrate the original prototype registration only when it identifies this
    # exact helper. Leave unrelated or manually customized registrations alone.
    try:
        previous = json.loads(target.read_text())
        previous_host = Path(previous["path"])
        same_helper = (
            previous == {**manifest, "path": str(previous_host)}
            and previous_host.is_absolute()
            and previous_host.name == "pdf_reload.py"
            and previous_host.read_bytes() == HOST_SOURCE
        )
    except (OSError, ValueError, TypeError, KeyError):
        same_helper = False
    if not same_helper:
        parser.error(f"Refusing to overwrite a different registration: {target}")
if host.exists() and not target.exists() and host.read_bytes() != HOST_SOURCE:
    parser.error(f"Refusing to overwrite an unregistered helper: {host}")


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(data)
            file.flush()
            os.fchmod(file.fileno(), mode)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


atomic_write(host, HOST_SOURCE, 0o700)
atomic_write(target, contents.encode(), 0o600)
print(f"Installed helper: {host}\nRegistered with Firefox: {target}\n"
      "You can now remove the downloaded installer.\n"
      "Open a local PDF in Firefox and click Local PDF Reload to watch it.")
