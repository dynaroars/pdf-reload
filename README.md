# Local PDF Reload for Firefox

I compile documents to PDF often and use Firefox’s built-in PDF viewer to read
them. This extension watches a local PDF and reloads the viewer when the file
actually changes, while letting Firefox preserve the current page, zoom, and
scroll position.

## Install

1. Install the add-on from [Firefox add-on website](https://addons.mozilla.org/en-US/firefox/addon/local-pdf-reload/).
2. You then will to paste this command into a terminal and run it:

   ```sh
   curl -fsSL https://github.com/dynaroars/pdf-reload/releases/latest/download/install-pdf-reload.sh | bash
   ```

   The installer, which only needs to **run ONCE**, registers the helper and verifies its  checksum. The
helper is needed because Firefox extensions cannot directly watch files on disk. No administrator access is needed.
   
*To use*: open a local .pdf in Firefox and click the Local PDF Reload toolbar button (in your Firefox extension list, you can also pin it to the tool bar for easier access).  Make sure to click it so that the icon changed to have the word *ON* on top of it. Now you can make changes to the pdf and Firefox will auto update the file.

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
