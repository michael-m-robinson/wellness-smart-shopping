#!/bin/bash
# Double-click this to open the Wellness Smart Shopping control panel.
cd "$(dirname "$0")" || exit 1
exec python3 panel.py "$@"
