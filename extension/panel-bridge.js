/*
 * Runs on local pages, but only does anything on the Wellness Smart Shopping
 * control panel (which carries <meta name="wss-panel">). It tells the panel the
 * Scanner is installed and relays scan requests to the extension, and progress
 * and results back.
 *
 * Page -> bridge:  {source: "wss-panel", type: "hello" | "scan" | "account", ...}
 * Bridge -> page:  {source: "wss-scanner", type: "ready" | "progress" | "result" | "account", ...}
 */
(function () {
  const version = chrome.runtime.getManifest().version;
  // The tag goes last, so no field in a relayed result can overwrite it.
  const post = (msg) => window.postMessage({ ...msg, source: "wss-scanner" },
                                           location.origin);
  let started = false;

  function start() {
    if (started || !document.querySelector('meta[name="wss-panel"]')) return;
    started = true;
    document.documentElement.dataset.wssScanner = version;

    window.addEventListener("message", (e) => {
      if (e.source !== window || !e.data || e.data.source !== "wss-panel") return;
      const d = e.data;
      if (d.type === "hello") post({ type: "ready", version });
      if (d.type === "account") {
        // Signed in to the store? Answered from a cookie's name only.
        chrome.runtime.sendMessage({ type: "wss-account", store: d.store })
          .then((r) => post({ type: "account", store: d.store, signedIn: r ? r.signedIn : null }))
          .catch(() => post({ type: "account", store: d.store, signedIn: null }));
      }
      if (d.type === "scan") {
        chrome.runtime.sendMessage({
          type: "wss-scan", store: d.store, name: d.name, adapter: d.adapter,
          url: d.url, panel: location.origin,
        }).then((result) => post({ type: "result", ...result }))
          .catch((err) => post({ type: "result", ok: false,
                                 error: "The Scanner extension stopped: " + err.message }));
      }
    });

    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && msg.type === "wss-progress") post({ type: "progress", text: msg.text });
    });

    post({ type: "ready", version });
  }

  // Injected at document_start, before the <meta> exists.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
