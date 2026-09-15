/* Firefox handles PDF position restoration when this is a genuine tab reload. */
const watched = new Map();
let port = null;

function openSetup() {
  browser.runtime.openOptionsPage().catch(() => {});
}

function pdfUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== "file:" || !/\.pdf$/i.test(url.pathname)) return null;
    url.hash = "";
    return url.href;
  } catch {
    return null;
  }
}

function badge(tabId, text, title) {
  // Tabs can close while a native message is in flight.
  browser.browserAction.setBadgeText({ tabId, text }).catch(() => {});
  browser.browserAction.setTitle({ tabId, title }).catch(() => {});
}

function sync() {
  if (!watched.size) {
    const old = port;
    port = null;
    old?.disconnect();
    return;
  }
  if (!port) {
    const connection = browser.runtime.connectNative("local_pdf_reload");
    port = connection;
    connection.onMessage.addListener(message => {
      if (port !== connection) return;
      for (const [tabId, url] of watched) {
        if (url !== message.url) continue;
        if (message.type === "changed") {
          reload(tabId, url);
        } else if (message.type === "error") {
          badge(tabId, "!", `PDF Reload: ${message.message}. Click to stop watching.`);
        } else if (message.type === "ready") {
          badge(tabId, "ON", "Watching this PDF. Click to stop.");
        }
      }
    });
    connection.onDisconnect.addListener(() => {
      if (port !== connection) return;
      port = null;
      for (const tabId of watched.keys()) {
        badge(tabId, "!", "PDF Reload helper unavailable. Install the helper, then click to retry.");
      }
      openSetup();
      watched.clear();
    });
  }
  port.postMessage({ type: "watch", urls: [...new Set(watched.values())] });
}

async function reload(tabId, expectedUrl) {
  try {
    const tab = await browser.tabs.get(tabId);
    if (watched.get(tabId) !== expectedUrl || pdfUrl(tab.url) !== expectedUrl) return;
    // Never navigate to a newly constructed URL: that loses PDF.js reload history.
    await browser.tabs.reload(tabId, { bypassCache: true });
    badge(tabId, "ON", "Watching this PDF. Click to stop.");
  } catch {
    if (watched.get(tabId) === expectedUrl) {
      badge(tabId, "!", "PDF reload failed. Click to stop watching.");
    }
  }
}

browser.browserAction.onClicked.addListener(tab => {
  if (watched.delete(tab.id)) {
    badge(tab.id, "", "Watch this local PDF");
    sync();
    return;
  }
  const url = pdfUrl(tab.url);
  if (!url) {
    badge(tab.id, "", "Open a local PDF (file://), then click to watch it.");
    return;
  }
  watched.set(tab.id, url);
  badge(tab.id, "ON", "Watching this PDF. Click to stop.");
  sync();
});

browser.tabs.onRemoved.addListener(tabId => {
  if (watched.delete(tabId)) sync();
});

browser.tabs.onUpdated.addListener((tabId, change) => {
  if (change.url && watched.has(tabId) && pdfUrl(change.url) !== watched.get(tabId)) {
    watched.delete(tabId);
    badge(tabId, "", "Watch this local PDF");
    sync();
  }
});
