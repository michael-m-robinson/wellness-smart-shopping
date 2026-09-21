/*
 * Wellness Smart Shopping Scanner - background worker.
 *
 * Opens the store page, runs that store's site file inside it (through
 * engine/engine.js), and posts the lines to the control panel's
 * /api/scan/submit. Posting from here rather than from the store page matters:
 * a public page is not allowed to reach a local address on its own, but an
 * extension with host access to 127.0.0.1 is.
 *
 * Every run's diagnostics also go to the panel (/api/scanner/report), which
 * keeps the latest per store on disk. When a site changes, that report says
 * which step and which selector stopped matching.
 *
 * Scans come from the panel's Scan button (via panel-bridge.js) and from the
 * toolbar popup. The popup can also "check" sites: run them and report
 * without filing anything.
 */

importScripts("engine/helpers.js", "sites/index.js");
importScripts(...Object.values(self.WSS_SITE_FILES));
const WSS = self.WSS;

const PORTS = [8765, 8766, 9000];
const MAX_HOPS = 3;       // landing page -> list page, and a spare

// ---------------------------------------------------------------- sites
function siteFor(name, store) {
  return WSS.sites[name] || WSS.sites[store] || WSS.sites.generic;
}

// Which store a page belongs to, from each site's hosts.
function storeForUrl(url) {
  let host = "";
  try { host = new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return ""; }
  for (const site of Object.values(WSS.sites)) {
    for (const domain of site.hosts || []) {
      if (host === domain || host.endsWith("." + domain)) return site.key;
    }
  }
  return "";
}

// ---------------------------------------------------------------- accounts
/*
 * Is the shopper signed in to a store whose deals need an account (ShopRite
 * coupons load only to a signed-in account)? Answers from the site file's
 * `account` block by looking for a cookie NAME. Cookie values -- the sign-in
 * token itself -- are never read, kept or sent anywhere.
 *   -> { store, signedIn: true | false | null }   null: this store has no check
 */
async function accountStatus(storeKey) {
  const site = WSS.sites[storeKey];
  const acct = site && site.account;
  if (!acct) return { store: storeKey, signedIn: null };
  const cookies = await chrome.cookies.getAll({ domain: acct.cookieDomain });
  const want = new RegExp(acct.signedInCookie, "i");
  const now = Date.now() / 1000;
  const signedIn = cookies.some((c) => want.test(c.name) &&
                                       (c.session || !c.expirationDate || c.expirationDate > now));
  return { store: storeKey, signedIn };
}

// ---------------------------------------------------------------- the panel
async function findPanel(preferred) {
  const bases = [];
  if (preferred) bases.push(preferred.replace(/\/+$/, ""));
  for (const port of PORTS) bases.push(`http://127.0.0.1:${port}`);
  for (const base of [...new Set(bases)]) {
    try {
      const r = await fetch(`${base}/api/state`, { cache: "no-store" });
      if (r.ok) {
        const state = await r.json();
        return { base, active: state.active !== false };
      }
    } catch (e) { /* not on this port */ }
  }
  return null;
}

async function listStores(preferred) {
  const panel = await findPanel(preferred);
  if (!panel) return { panel: null, stores: [] };
  try {
    const r = await fetch(`${panel.base}/api/stores`, { cache: "no-store" });
    if (r.ok) return { panel, stores: (await r.json()).stores || [] };
  } catch (e) { /* an older panel without /api/stores */ }
  return { panel, stores: [] };
}

async function submit(base, store, lines) {
  const r = await fetch(`${base}/api/scan/submit?store=${encodeURIComponent(store)}`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: lines.join("\n"),
  });
  let body = {};
  try { body = await r.json(); } catch (e) { /* not JSON */ }
  if (r.status === 409) throw new Error("The control panel is paused. Switch it on and scan again.");
  if (r.status === 404) throw new Error(`The control panel does not know a store called "${store}".`);
  if (!r.ok) throw new Error(body.error || `The control panel answered ${r.status}.`);
  return body;
}

// Best effort: a report that cannot be filed must not fail the scan.
async function report(panel, key, result, extra = {}) {
  if (!panel || !result) return;
  const body = { at: new Date().toISOString(), ...(result.diagnostics || {}),
                 ok: !!result.ok, error: result.error || "",
                 scanner: chrome.runtime.getManifest().version, ...extra };
  try {
    await fetch(`${panel.base}/api/scanner/report?store=${encodeURIComponent(key)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) { /* the panel went away */ }
}

// ---------------------------------------------------------------- tabs
function waitForLoad(tabId, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listen);
      reject(new Error("The store page took too long to load."));
    }, timeoutMs);
    function listen(id, info) {
      if (id === tabId && info.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listen);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listen);
    chrome.tabs.get(tabId).then((t) => {
      if (t.status === "complete") listen(tabId, { status: "complete" });
    }).catch(() => {});
  });
}

async function runSite(tabId, site) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["engine/helpers.js", "engine/engine.js", self.WSS_SITE_FILES[site.key]],
  });
  const [res] = await chrome.scripting.executeScript({
    target: { tabId },
    args: [site.key],
    // Runs in the page's isolated world, where the files just landed.
    // Progress messages also keep this worker awake during a long scroll.
    func: (key) => globalThis.WSS.run(globalThis.WSS.sites[key], {
      progress: (text) => chrome.runtime.sendMessage({ type: "wss-progress", text }).catch(() => {}),
    }),
  });
  if (!res || !res.result) throw new Error("The scanner did not return a result.");
  return res.result;
}

// Run a site on a tab, following its discover link to the real list.
async function runWithHops(tabId, site) {
  let result;
  for (let hop = 0; hop <= MAX_HOPS; hop++) {
    await waitForLoad(tabId);
    try {
      result = await runSite(tabId, site);
    } catch (e) {
      if (/cannot access|permission/i.test(String(e.message))) {
        throw new Error("Chrome has not given the Scanner access to this site. " +
                        "Open the page and press the Scanner's toolbar button there.");
      }
      throw e;
    }
    if (!result.navigate) return result;
    tell({ type: "wss-progress", text: `Opening ${site.name}'s list...` });
    await chrome.tabs.update(tabId, { url: result.navigate });
    await new Promise((r) => setTimeout(r, 500));
  }
  return { ok: false, error: `${site.name} kept redirecting; the scan stopped.`,
           diagnostics: result && result.diagnostics };
}

// ---------------------------------------------------------------- scanning
let current = null;           // one scan at a time
let listener = null;          // the panel tab to tell about progress

function tell(message) {
  if (listener) chrome.tabs.sendMessage(listener, message).catch(() => {});
  chrome.runtime.sendMessage(message).catch(() => {});   // an open popup
}

async function remember(result) {
  const { diagnostics, ...kept } = result;
  await chrome.storage.local.set({ lastScan: { ...kept, at: Date.now() } });
  return result;
}

/*
 * job: { store, name?, adapter?, url?, tabId?, panel?, returnTo?, check? }
 *   url   - open this page (the site's own startUrl wins)
 *   tabId - scan this tab instead of opening one (popup)
 *   check - run and report, file nothing
 */
async function scan(job) {
  if (current) return { ok: false, error: "A scan is already running." };
  current = job;
  listener = job.returnTo || null;
  const site = siteFor(job.adapter, job.store);
  const label = job.name || (site.key !== "generic" ? site.name : job.store) || "this page";
  let opened = null;
  let panel = null;

  try {
    // From the panel, no panel means nothing to file with. From the popup,
    // scan anyway: the offers can still be copied.
    panel = await findPanel(job.panel);
    const unfiled = !panel
      ? "The control panel is not running. Start it (python3 panel.py, or the app)."
      : !panel.active ? "The control panel is paused. Switch it on to file scans." : "";
    if (unfiled && !job.tabId && !job.check) throw new Error(unfiled + " Then scan again.");

    let tabId = job.tabId;
    if (tabId && site.readableOn) {
      // Pressed on a page the site does not read (shoprite.com, or Stew's
      // image flyer): start from the site's own page instead.
      const tab = await chrome.tabs.get(tabId);
      if (!new RegExp(site.readableOn).test(tab.url || "")) tabId = null;
    }
    if (!tabId) {
      const url = site.startUrl || job.url;
      if (!url) throw new Error(`No page is set up to scan for ${label}.`);
      tell({ type: "wss-progress", text: `Opening ${label}...` });
      opened = await chrome.tabs.create({ url, active: true });
      tabId = opened.id;
    }

    tell({ type: "wss-progress", text: `Reading ${label}...` });
    const result = await runWithHops(tabId, site);
    const key = job.store || site.key;
    await report(panel, key, result, { check: !!job.check });

    if (!result.ok) {
      // Leave the tab open: a sign-in prompt or a short list is worth seeing.
      opened = null;
      return await remember({ ok: false, store: job.store, name: label, check: !!job.check,
                              error: result.error, lines: result.lines || [],
                              checks: result.checks || null, diagnostics: result.diagnostics });
    }
    if (job.check) {
      return await remember({ ok: true, check: true, store: key, name: label,
                              count: result.lines.length, checks: result.checks,
                              lines: result.lines, diagnostics: result.diagnostics });
    }
    const store = job.store;
    if (unfiled) {
      return await remember({ ok: false, store, name: label, lines: result.lines,
                              error: unfiled + " Here are the offers to copy." });
    }
    if (!store) {
      return await remember({ ok: false, name: label, lines: result.lines,
                              error: "Pick which store this page belongs to, then scan again." });
    }
    const saved = await submit(panel.base, store, result.lines);
    return await remember({ ok: true, store, name: saved.store || label,
                            count: saved.lines, checks: result.checks || null,
                            lines: result.lines,
                            // The page the offers came from (Stew's changes weekly).
                            pageUrl: (result.diagnostics && result.diagnostics.url) || "" });
  } catch (e) {
    opened = null;
    const failed = { ok: false, store: job.store, name: label, error: String(e.message || e) };
    await report(panel, job.store || site.key, failed, { site: site.key, check: !!job.check });
    return await remember(failed);
  } finally {
    if (opened) chrome.tabs.remove(opened.id).catch(() => {});
    if (job.returnTo) chrome.tabs.update(job.returnTo, { active: true }).catch(() => {});
    current = null;
    listener = null;
  }
}

// Check every named site in turn, filing nothing. The reports land in the
// panel's data folder, one per store.
async function checkAll() {
  const out = [];
  for (const site of Object.values(WSS.sites)) {
    if (site.key === "generic") continue;
    const r = await scan({ store: site.key, name: site.name, check: true });
    out.push({ store: site.key, name: site.name, ok: r.ok, count: r.count || 0,
               error: r.error || "", checks: r.checks || null });
  }
  await chrome.storage.local.set({ lastCheck: { at: Date.now(), sites: out } });
  return out;
}

// ---------------------------------------------------------------- messages
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || typeof msg !== "object") return false;

  if (msg.type === "wss-progress" && sender.tab && current) {
    // From the engine inside the store page: pass it on.
    tell({ type: "wss-progress", text: msg.text });
    return false;
  }

  if (msg.type === "wss-scan") {
    // From the panel page, through panel-bridge.js.
    scan({ store: msg.store, name: msg.name, adapter: msg.adapter,
           url: msg.url, panel: msg.panel,
           returnTo: sender.tab ? sender.tab.id : null }).then(reply);
    return true;
  }

  if (msg.type === "wss-scan-tab") {
    // From the popup: scan (or check) the tab it was opened on.
    scan({ store: msg.store, name: msg.name, adapter: msg.adapter,
           tabId: msg.tabId, check: !!msg.check }).then(reply);
    return true;
  }

  if (msg.type === "wss-account") {
    // From the panel (through the bridge) or the popup.
    accountStatus(String(msg.store || "")).then(reply)
      .catch(() => reply({ store: msg.store, signedIn: null }));
    return true;
  }

  if (msg.type === "wss-check-all") {
    checkAll().then(reply);
    return true;
  }

  if (msg.type === "wss-status") {
    chrome.tabs.get(msg.tabId).then(async (tab) => {
      const { panel, stores } = await listStores();
      const { lastScan, lastCheck } = await chrome.storage.local.get(["lastScan", "lastCheck"]);
      const sites = Object.values(WSS.sites).map((s) => ({
        key: s.key, name: s.name, version: s.version, verified: s.verified }));
      reply({ panel, stores, sites, busy: !!current, lastScan, lastCheck,
              guess: storeForUrl(tab.url || ""), url: tab.url || "" });
    }).catch((e) => reply({ error: String(e.message || e) }));
    return true;
  }

  return false;
});
