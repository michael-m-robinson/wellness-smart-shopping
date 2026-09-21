# Requirements

**No Python packages are needed.** The crawler, the control panel and the
installer are standard library only, and the desktop app uses Apple's own
frameworks with no Swift package dependencies. There is nothing to vendor and
nothing to keep up to date -- `requirements.txt` here is deliberately empty.

What the project needs instead is a few tools. `../install.command` checks all
of them, tells you which are missing, and offers to set up what it safely can.

**Two routes. Terminal is the one to start with.**

| Route | What you run | |
| --- | --- | --- |
| **Terminal** — recommended | `python3 panel.py`, or `python3 crawl.py` | Config, scans and sales files all sit in the folder you cloned |
| **Desktop app** | Drag it in from the disk image, press **Scan with Claude** | Adds meal plans, recipes and PDFs; keeps its files in `~/Library/Application Support/` |

Both open the same control panel and produce the same file. The scan
instruction is identical either way — it names no folder and no file.

Terminal is recommended because everything stays in one visible folder. The
app keeps its data in Application Support, which is correct for an installed
app but puts your files somewhere other tools may not be permitted to read.

Then, whichever route you took:Then, whichever route you took:

| Requirement | Needed for | How to get it |
| --- | --- | --- |
| macOS 13 or newer | The desktop app (Terminal route works anywhere Python does) | — |
| Python 3.9+ | The control panel and the crawler | Ships with the Xcode command line tools as `/usr/bin/python3`; or python.org; or `brew install python` |
| Xcode command line tools | Building the desktop app from `app/` | `xcode-select --install` |
| Google Chrome, or Edge, Brave, Arc | Scanning store pages | google.com/chrome |
| Claude for Chrome extension | Scanning store pages | [Chrome Web Store](https://chromewebstore.google.com/detail/fcoeoabgfenejglbffodgkkbkcdhcgfn) |
| A Claude subscription | Scanning store pages | claude.ai |

Python is the only hard requirement for the Terminal route. The Xcode tools
matter only if you build the app yourself rather than using one someone else
built. Chrome, the extension and the subscription matter only for scanning --
importing a sales file by hand works without any of them.

After a run, `detected.txt` records what was actually found on this machine.
