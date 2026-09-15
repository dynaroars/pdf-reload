#!/usr/bin/env python3
"""Opt-in integration test using an isolated headless Firefox and real LaTeX.

Uses privileged Marionette inspection only in the disposable test profile.
The extension itself has no privileged access to the viewer.
"""

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


class Marionette:
    def __init__(self, port):
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.sequence = 0
        self.receive()
        self.call("WebDriver:NewSession", {"capabilities": {}})

    def receive(self):
        prefix = b""
        while not prefix.endswith(b":"):
            chunk = self.socket.recv(1)
            if not chunk:
                raise EOFError("Firefox disconnected")
            prefix += chunk
        remaining = int(prefix[:-1])
        data = b""
        while remaining:
            chunk = self.socket.recv(remaining)
            if not chunk:
                raise EOFError("Firefox disconnected")
            data += chunk
            remaining -= len(chunk)
        return json.loads(data)

    def call(self, command, params=None):
        self.sequence += 1
        data = json.dumps([0, self.sequence, command, params or {}]).encode()
        self.socket.sendall(str(len(data)).encode() + b":" + data)
        response = self.receive()
        if response[2]:
            raise RuntimeError(response[2])
        return response[3]

    def execute(self, script, args=None, context="content"):
        self.call("Marionette:SetContext", {"value": context})
        result = self.call("WebDriver:ExecuteScript", {
            "script": script, "args": args or [], "newSandbox": True,
            "sandbox": "default", "line": 1, "filename": "firefox_smoke.py",
        })
        return result.get("value")

def wait_for(callback, timeout=20):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = callback()
            if result:
                return result
        except (RuntimeError, KeyError) as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError(f"Timed out: {last_error}")


STATE = """
const app = window.wrappedJSObject.PDFViewerApplication;
if (!app?.pdfDocument || !app.pdfViewer._location) return null;
return {fingerprint: app.pdfDocument.fingerprints[0],
        page: app.page, scale: app.pdfViewer.currentScaleValue,
        location: {...app.pdfViewer._location},
        top: app.pdfViewer.container.scrollTop};
"""

CLICK = """
const {ExtensionParent} = ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs');
const extension = WebExtensionPolicy.getByID('pdf-reload@local').extension;
const action = ExtensionParent.apiManager.global.browserAction.for(extension);
action.action.dispatchClick(window.gBrowser.selectedTab, {button: 0, modifiers: []});
return true;
"""


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/package.py")], check=True)
    version = json.loads((ROOT / "extension/manifest.json").read_text())["version"]
    package = ROOT / "dist" / f"local-pdf-reload-{version}-unsigned.xpi"
    with tempfile.TemporaryDirectory(prefix="pdf-reload-firefox-") as temporary:
        temp = Path(temporary)
        profile = temp / "profile"
        profile.mkdir()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        (profile / "user.js").write_text(
            f'user_pref("marionette.port", {port});\n'
            'user_pref("browser.shell.checkDefaultBrowser", false);\n'
            'user_pref("browser.startup.homepage_override.mstone", "ignore");\n'
        )
        native_root = temp / "native"
        subprocess.run([sys.executable, str(ROOT / "dist/install-pdf-reload.py"),
                        "--manifest-dir", str(native_root / "native-messaging-hosts"),
                        "--install-dir", str(temp / "helper")], check=True)
        tex = temp / "document.tex"

        def compile_pdf(version):
            tex.write_text(r"\documentclass{article}\begin{document}" + "\n" +
                           "\n\\newpage\n".join(
                               f"Page {page}. Version {version}.\\par\n" +
                               ("Some text to inspect while recompiling.\\par\n" * 18)
                               for page in range(1, 6)) + r"\end{document}")
            subprocess.run(["pdflatex", "-interaction=batchmode", "-halt-on-error",
                            f"-output-directory={temp}", str(tex)],
                           check=True, stdout=subprocess.DEVNULL)

        compile_pdf(1)
        with (temp / "firefox.log").open("w+") as log:
            process = subprocess.Popen([
                "firefox", "--headless", "--no-remote", "--profile", str(profile),
                "--marionette", "--remote-allow-system-access", "about:blank",
            ], stdout=log, stderr=log)
            try:
                def connect():
                    try:
                        return Marionette(port)
                    except OSError:
                        if process.poll() is not None:
                            raise RuntimeError("Firefox exited")
                        return None

                client = wait_for(connect)
                # Direct native-host discovery to this test's private registration.
                client.execute("""
                    const file = Cc['@mozilla.org/file/local;1'].createInstance(Ci.nsIFile);
                    file.initWithPath(arguments[0]);
                    Services.dirsvc.set('XREUserNativeManifests', file);
                    return true;
                """, [str(native_root)], context="chrome")
                client.call("Addon:Install", {"path": str(package), "temporary": True})
                client.call("Marionette:SetContext", {"value": "content"})
                client.call("WebDriver:Navigate", {"url": (temp / "document.pdf").as_uri()})
                wait_for(lambda: client.execute(STATE))
                client.execute("""
                    const app = window.wrappedJSObject.PDFViewerApplication;
                    app.pdfViewer.currentScaleValue = '1.25';
                    app.pdfViewer.scrollPageIntoView({pageNumber: 3,
                        destArray: [null, {name: 'XYZ'}, 0, 600, null]});
                """)
                time.sleep(1.5)
                before = client.execute(STATE)
                assert before["page"] == 3, before
                client.execute(CLICK, context="chrome")
                time.sleep(0.5)
                compile_pdf(2)
                after = wait_for(lambda: (
                    state if (state := client.execute(STATE)) and
                    state["fingerprint"] != before["fingerprint"] else None))
                time.sleep(1)
                after = client.execute(STATE)
                assert after["page"] == before["page"], (before, after)
                assert after["scale"] == before["scale"], (before, after)
                assert abs(after["top"] - before["top"]) <= 2, (before, after)
                print(json.dumps({"before": before, "after": after}, indent=2))
                print("PASS: native helper -> extension -> real PDF reload; page, zoom, scroll retained.")
                client.execute(CLICK, context="chrome")
                compile_pdf(3)
                time.sleep(2)
                assert client.execute(STATE)["fingerprint"] == after["fingerprint"]
                print("PASS: disabling watch prevents reload.")
                client.call("Marionette:Quit", {"flags": ["eForceQuit"]})
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read()[-6000:], file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
