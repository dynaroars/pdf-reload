#!/usr/bin/env python3
"""Build the unsigned Firefox XPI and a standalone Linux helper installer."""

import json
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
extension = ROOT / "extension"
manifest = json.loads((extension / "manifest.json").read_text())
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
archive = dist / f"local-pdf-reload-{manifest['version']}-unsigned.xpi"
files = ["manifest.json", "background.js", "setup.html", "setup.js", "icon.svg"]
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
    for name in files:
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        output.writestr(info, (extension / name).read_bytes())

installer = (ROOT / "native/install.py").read_text()
source_line = 'HOST_SOURCE = Path(__file__).with_name("pdf_reload.py").read_bytes()'
assert installer.count(source_line) == 1
installer = installer.replace(source_line,
                              "HOST_SOURCE = " + repr((ROOT / "native/pdf_reload.py").read_bytes()))
target = dist / "install-pdf-reload.py"
target.write_text(installer)
checksum = hashlib.sha256(target.read_bytes()).hexdigest()
(dist / "SHA256SUMS").write_text(f"{checksum}  install-pdf-reload.py\n")
shell_installer = dist / "install-pdf-reload.sh"
shell_installer.write_text((ROOT / "scripts/install-pdf-reload.sh").read_text())
shell_installer.chmod(0o755)
print(f"Built {archive}\nBuilt {target}\n"
      "The XPI is unsigned. Submit it to Mozilla for signing before normal Firefox installation.")
