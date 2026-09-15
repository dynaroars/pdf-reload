# Local PDF Reload for Firefox

I compile documents to PDF often and use Firefox’s built-in PDF viewer to read
them. This extension watches a local PDF and reloads the viewer when the file
actually changes, while letting Firefox preserve the current page, zoom, and
scroll position.

## Install

The add-on must be signed by Mozilla before regular Firefox can install it. The
helper is needed because Firefox extensions cannot directly watch files on disk.

1. Install the signed XPI from the [latest release][release].
2. If Firefox reports that the helper is missing, open the extension setup page
   and paste this command into a terminal:

   ```sh
   curl -fsSL https://github.com/dynaroars/pdf-reload/releases/latest/download/install-pdf-reload.sh | bash
   ```

   The installer, which only needs to **run ONCE**, registers the helper for your account and verifies its
   checksum. No administrator access is needed.
3. After installing, open a local `.pdf` in Firefox and click the Local PDF Reload toolbar button (in your Firefox extension list, you can also pin it to the tool bar for easier access).

The helper sends file-change notices only; it does not send PDF contents over
the network. Watching stops when you disable the button, close the tab, or
navigate away.

Licensed under the [MIT License](LICENSE).

## Development

This project currently targets Linux and requires Python 3.11+. To build the
XPI and standalone installer:

```sh
python3 scripts/package.py
```

Run the checks with:

```sh
python3 -m unittest discover -s tests
node --check extension/background.js
```

[release]: https://github.com/dynaroars/pdf-reload/releases
