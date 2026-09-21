/*
 * The toolbar popup: scan whatever store page is open, file it with the panel,
 * and show the last result. If the panel cannot take the offers, they are shown
 * here to copy rather than lost.
 */
const $ = (id) => document.getElementById(id);
let tab = null;
let storeList = [];

// Logged in to the stores whose coupons need an account (ShopRite)? Only
// used to word a scan result. The answer comes from a cookie's name only.
const loginState = {};
async function checkLogins() {
  for (const s of storeList) {
    if (!s.redeem || !s.redeem.signed_in) continue;
    const site = s.adapter && s.adapter !== "generic" ? s.adapter : s.key;
    const r = await chrome.runtime.sendMessage({ type: "wss-account", store: site });
    loginState[s.key] = r ? r.signedIn : null;
  }
}

// After a filed scan: what the store needs before the deals count (ShopRite:
// load the coupons to your signed-in account). Notices come from the panel.
function showRedeem(storeKey) {
  const s = storeList.find((x) => x.key === storeKey);
  const r = s && s.redeem;
  $("redeem").hidden = !(r && r.title);
  if (!r || !r.title) return;
  const words = r.level === "action" && loginState[storeKey] === true && r.signed_in ? r.signed_in : r;
  $("redeem").className = "redeem " + (r.level === "action" ? "action" : "info");
  $("redeem-title").textContent = words.title;
  $("redeem-body").textContent = words.body || "";
  const a = $("redeem-link");
  a.hidden = !(r.link && r.link.url);
  if (!a.hidden) { a.href = r.link.url; a.textContent = r.link.label || "Open"; }
}

function status(text, kind = "") {
  $("status").textContent = text || "";
  $("status").className = kind;
}

function showResult(r) {
  if (!r) return;
  if (r.check) {
    status(r.ok ? `${r.name}: check passed - ${r.count} offers read. Nothing was filed.`
                : `${r.name}: check failed. ${r.error}`, r.ok ? "good" : "bad");
    $("result").hidden = !(r.lines || []).length;
    $("lines").value = (r.lines || []).join("\n");
    return;
  }
  const when = r.at ? new Date(r.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
  showRedeem(r.ok ? r.store : "");
  if (r.ok) {
    status(`${r.name}: sent ${r.count} offers to the panel${when ? " at " + when : ""}.`, "good");
  } else {
    status(r.error || "The scan did not finish.", "bad");
  }
  const lines = r.lines || [];
  $("result").hidden = r.ok || !lines.length;
  $("lines").value = lines.join("\n");
}

function fillStores(stores, guess) {
  const pick = $("store");
  pick.textContent = "";
  const list = stores.length ? stores
    : [{ key: "shoprite", name: "ShopRite" }, { key: "stews", name: "Stew Leonard's" },
       { key: "costco", name: "Costco" }];
  if (!guess) pick.append(new Option("Choose a store...", ""));
  for (const s of list) {
    const o = new Option(s.name, s.key);
    o.dataset.adapter = s.adapter || "";
    pick.append(o);
  }
  if (guess) pick.value = guess;
}

async function load() {
  [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const st = await chrome.runtime.sendMessage({ type: "wss-status", tabId: tab.id });
  if (st.error) { status(st.error, "bad"); return; }

  if (!st.panel) {
    $("panel").textContent = "The control panel is not running. Start it " +
      "(python3 panel.py, or the app) to file scans. You can still scan and copy.";
  } else if (!st.panel.active) {
    $("panel").textContent = "The control panel is paused. Switch it on to file scans.";
  } else {
    $("panel").textContent = `Control panel ready at ${st.panel.base.replace("http://", "")}.`;
  }

  storeList = st.stores || [];
  fillStores(storeList, st.guess);
  // No deals on hand this week: say what a scan is worth.
  $("save").hidden = !(st.panel && st.panel.deals && st.panel.deals.count === 0);
  checkLogins();
  paintSites(st.sites || [], st.lastCheck);
  if (!/^https?:/.test(st.url)) {
    $("go").disabled = true;
    status("Open a store's coupon list or weekly ad, then press the button again.");
  }
  if (st.busy) {
    $("go").disabled = true;
    status("A scan is running...");
  } else if (st.lastScan) {
    showResult(st.lastScan);
  }
}

$("go").onclick = async () => {
  const pick = $("store");
  const opt = pick.selectedOptions[0];
  $("go").disabled = true;
  $("result").hidden = true;
  status("Scanning... this can take half a minute on a long list.");
  const r = await chrome.runtime.sendMessage({
    type: "wss-scan-tab", tabId: tab.id, store: pick.value,
    name: opt && opt.value ? opt.textContent : "",
    adapter: opt ? opt.dataset.adapter : "",
  });
  $("go").disabled = false;
  showResult(r);
};

// Each site file's version and when it was last verified, plus the last check.
function paintSites(sites, lastCheck) {
  const results = {};
  for (const s of (lastCheck && lastCheck.sites) || []) results[s.store] = s;
  const list = $("sites");
  list.textContent = "";
  for (const s of sites) {
    if (s.key === "generic") continue;
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = `${s.name} v${s.version} - verified ${s.verified}`;
    const last = document.createElement("span");
    const r = results[s.key];
    last.textContent = r ? (r.ok ? `ok, ${r.count}` : "failed") : "";
    last.className = r ? (r.ok ? "ok" : "bad") : "";
    if (r && !r.ok) last.title = r.error;
    li.append(name, last);
    list.append(li);
  }
}

$("check").onclick = async () => {
  const pick = $("store");
  const opt = pick.selectedOptions[0];
  $("check").disabled = $("go").disabled = true;
  status("Checking... nothing will be filed.");
  const r = await chrome.runtime.sendMessage({
    type: "wss-scan-tab", tabId: tab.id, store: pick.value, check: true,
    name: opt && opt.value ? opt.textContent : "", adapter: opt ? opt.dataset.adapter : "",
  });
  $("check").disabled = $("go").disabled = false;
  showResult(r);
};

$("checkall").onclick = async () => {
  $("checkall").disabled = $("check").disabled = $("go").disabled = true;
  status("Checking every site in turn. Each opens in a tab; leave them in front.");
  const results = await chrome.runtime.sendMessage({ type: "wss-check-all" });
  $("checkall").disabled = $("check").disabled = $("go").disabled = false;
  const failed = results.filter((r) => !r.ok);
  status(failed.length ? `${failed.length} of ${results.length} sites failed: ` +
                         failed.map((r) => r.name).join(", ") + ". The reports say why."
                       : `All ${results.length} sites passed.`, failed.length ? "bad" : "good");
  const st = await chrome.runtime.sendMessage({ type: "wss-status", tabId: tab.id });
  paintSites(st.sites || [], st.lastCheck);
};

$("copy").onclick = async () => {
  await navigator.clipboard.writeText($("lines").value);
  $("copy").textContent = "Copied";
  setTimeout(() => ($("copy").textContent = "Copy offers"), 1500);
};

chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "wss-progress" && $("go").disabled) status(msg.text);
});

load();
