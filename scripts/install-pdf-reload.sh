#!/bin/sh
set -eu

base_url="https://github.com/dynaroars/pdf-reload/releases/latest/download"
temporary="$(mktemp)"
checksums="$(mktemp)"
trap 'rm -f "$temporary" "$checksums"' EXIT

if ! command -v python3 >/dev/null 2>&1; then
  echo "Local PDF Reload needs Python 3.11 or newer." >&2
  echo "Install Python 3.11+, then run this command again." >&2
  exit 1
fi

curl -fsSL "$base_url/install-pdf-reload.py" -o "$temporary"
curl -fsSL "$base_url/SHA256SUMS" -o "$checksums"
expected="$(awk '$2 == "install-pdf-reload.py" {print $1}' "$checksums")"
actual="$(sha256sum "$temporary" | awk '{print $1}')"
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
  echo "Checksum verification failed for the helper installer." >&2
  exit 1
fi
exec python3 "$temporary"
