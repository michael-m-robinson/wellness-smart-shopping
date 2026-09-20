# Requirements

**No Python packages are needed.** The crawler, the control panel and the
installer are standard library only, and the desktop app uses Apple's own
frameworks with no Swift package dependencies. There is nothing to vendor and
nothing to keep up to date -- `requirements.txt` here is deliberately empty.

What the project needs instead is a few tools. `../install.command` checks all
of them, tells you which are missing, and offers to set up what it safely can.

| Requirement | Needed for | How to get it |
| --- | --- | --- |
| macOS 13 or newer | The desktop app | — |
| Python 3.9+ | Crawler, control panel, installer | Ships with the Xcode command line tools as `/usr/bin/python3`; or python.org; or `brew install python` |
| Xcode command line tools | Building the desktop app from `app/` | `xcode-select --install` |
| Google Chrome | Scanning store pages | google.com/chrome |
| Claude for Chrome extension | Scanning store pages | [Chrome Web Store](https://chromewebstore.google.com/detail/fcoeoabgfenejglbffodgkkbkcdhcgfn) |
| A Claude subscription | Scanning store pages | claude.ai |

Only the first two are needed to run the control panel and produce a sales
file. The Xcode tools matter only if you build the app yourself rather than
using one someone else built. Chrome, the extension and the subscription matter
only for scanning -- importing a sales file by hand works without them.

After a run, `detected.txt` records what was actually found on this machine.
