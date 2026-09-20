# Scans land here

One file per store, named after its key in `config.json`:

```
harvest/shoprite.txt
harvest/stews.txt
harvest/costco.txt
```

To make one: sign in to the store in Chrome, open its weekly ad or digital
coupon list, and ask Claude (with the Claude for Chrome extension enabled) to
run `browser/harvest.js` on that tab. Save what it prints here.

Then press **Refresh Deals** in the control panel, or run `python3 crawl.py`.

The `.txt` files are git-ignored -- they are your shopping data, not the project's.
