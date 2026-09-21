/*
 * Every site the Scanner knows. Adding a store: write sites/<key>.js (see
 * sites/README.md), add it here, and add its domain to host_permissions in
 * manifest.json. The key must match the store's key in the panel's config
 * (or the store's "adapter" setting).
 */
globalThis.WSS_SITE_FILES = {
  shoprite: "sites/shoprite.js",
  stews: "sites/stews.js",
  costco: "sites/costco.js",
  generic: "sites/generic.js",
};
