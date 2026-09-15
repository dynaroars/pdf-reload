# Local PDF Reload for Firefox on Linux

A small Firefox extension and Python helper that keep the built-in PDF viewer.
Click the toolbar button on a local PDF to watch it; click again to stop.
Only changed PDF contents trigger a reload. Watching stops when you close the
tab, navigate to another file, or restart Firefox.

## Install in Firefox

Requires a normal Linux Firefox installation. Snap and Flatpak Firefox may need
additional native messaging integration; the installer does not configure those
packages. No administrator privileges are needed.

The browser add-on can be installed through Firefox once Mozilla signs it.
The current build is **unsigned**: normal Firefox will reject it through
**Install Add-on From File** until that signing step is completed.

### One-time release preparation: Mozilla signing

The ready-to-upload package is `dist/local-pdf-reload-0.1.0-unsigned.xpi`.
To regenerate the package and helper installers, run
`python3 scripts/package.py`.

1. Sign in to the [Mozilla Add-on Developer Hub](https://addons.mozilla.org/developers/).
2. Submit a new add-on and choose **On your own** (unlisted/self-distributed).
3. Upload `dist/local-pdf-reload-0.1.0-unsigned.xpi` and complete the submission.
   The extension uses plain JavaScript, with no minification or build step.
4. Once Mozilla has signed it, download the **signed** `.xpi` from the submission.

Signing does not require a public listing. This project has not yet been
submitted; it requires a Mozilla developer account.
See [Mozilla's signing guide](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).

### Installation

1. In Firefox, open `about:addons`, click the gear menu, choose
   **Install Add-on From File…**, and select the **signed** `.xpi`.
2. If the helper is missing, open the extension’s setup page and paste its
   one-line installer command into a terminal. It downloads and runs the
   per-user installer; users do not need to know the helper is Python:
   `curl -fsSL https://github.com/dynaroars/pdf-reload/releases/latest/download/install-pdf-reload.sh | bash`.
   The same installer is available as `dist/install-pdf-reload.sh` in a source
   checkout.
3. Open your local PDF and click **Local PDF Reload** in the toolbar to watch it.
   **ON** means watching. Click again to stop. **!** indicates an error; hover
   over the button for details.

The helper installer is self-contained. It copies the helper to
`~/.local/share/local-pdf-reload/` and registers it with Firefox. You can delete
the downloaded installer and the project checkout afterward. The signed add-on
stays installed across restarts; click its button to enable watching each session.

Firefox cannot execute the native installer itself; the terminal command is the
one user action required by this design. The helper starts on demand and exits
when there are no watched tabs.

To uninstall, remove the add-on in Firefox and delete these two files:

- `~/.mozilla/native-messaging-hosts/local_pdf_reload.json`
- `~/.local/share/local-pdf-reload/pdf_reload.py`

### Development: temporary installation without signing

1. From this checkout, run `python3 native/install.py` to register the helper.
2. Open `about:debugging#/runtime/this-firefox` in Firefox.
3. Click **Load Temporary Add-on**, then select `extension/manifest.json`.
4. Open your local PDF, pin **Local PDF Reload** to the toolbar if needed, and
   click its button. **ON** means watching. **!** indicates an error; hover over
   the button for details.

The temporary add-on must be loaded again after restarting Firefox. Permanent
installation in regular Firefox requires a Mozilla-signed extension, which can
be distributed privately. This prototype has not been submitted for signing.

The installer automatically migrates the original prototype registration when
it points to an identical helper. It refuses to overwrite other registrations.

## Reading position

The extension uses `browser.tabs.reload(tabId, {bypassCache: true})`. Firefox's
PDF.js viewer restores its own history on a genuine reload, including when a
PDF's fingerprint changes. It does not navigate to a new URL or add cache-busting
query parameters. No `about:config` changes or PDF-viewer script injection are used.

Position preservation means page number and view coordinates, not tracking the
same paragraph if LaTeX moves it to another page. Deleting the page you were on
cannot preserve that page. Reloading still redraws the viewer and can briefly
flash; text selection, search state and unsaved PDF edits are not guaranteed to
survive. Use this for generated PDF previews.

## File change detection

The dependency-free helper polls file metadata every 250 ms, waits for one second
of unchanged metadata, checks the PDF header and final `%%EOF`, then hashes the
contents. Touching or rewriting identical bytes does not reload the tab. It
handles atomic replacement, temporary deletion, and incomplete output while
keeping the old PDF visible until a complete changed file is available.

The settle delay and EOF check are heuristics, not a signal that a multi-pass
LaTeX build has finished. If a build pauses on a complete intermediate PDF for
over a second, it can cause an intermediate reload. `SETTLE_SECONDS` in
`native/pdf_reload.py` controls the delay.

Permissions: `tabs` identifies the selected PDF tab; `nativeMessaging` talks to
the local helper. Only files explicitly enabled with the button are watched.
The helper sends change notices, not PDF contents. There are no network requests.

## Checks

Run `python3 -m unittest discover -s tests` and
`node --check extension/background.js`.

`python3 tests/firefox_smoke.py` runs a full integration test with Firefox and
`pdflatex`. It builds and loads the packaged XPI, runs the standalone installer,
and creates a disposable headless Firefox profile and private native
host registration under `/tmp`, without installing anything in your normal
profile. Browser automation requires permission to use a loopback socket.

Verified on Firefox 155.0 on Linux: recompiling a five-page LaTeX document changed
its fingerprint, triggered an automatic reload through the actual extension and
native helper, and preserved page 3, 125% zoom, and scroll offset exactly
(3241 pixels before and after). Disabling watching prevented a further reload.
This verifies that scenario, not every PDF layout change or Firefox version.

Upstream implementation reference:
[PDF.js reload history restoration](https://github.com/mozilla/pdf.js/blob/master/web/pdf_history.js).

For a manual acceptance test, open a multi-page LaTeX PDF, scroll partway through
page 3, change zoom, and recompile. Confirm new content appears at the same page
and view position. Also try rapid compiles, a failed compile, a filename with
spaces, and switching away from the PDF tab.
