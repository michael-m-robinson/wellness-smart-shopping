#!/bin/bash
# Double-click to set up Wellness Smart Shopping.
cd "$(dirname "$0")" || exit 1
python3 installer.py "$@"
status=$?
echo
read -r -p "Press Return to close this window. "
exit $status
