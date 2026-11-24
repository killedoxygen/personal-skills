#!/bin/sh
# Compatibility wrapper: the installer is install.py (Python 3.9+, stdlib only).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for python in python3 python; do
  if command -v "$python" >/dev/null 2>&1; then
    exec "$python" "$here/install.py" "$@"
  fi
done
echo "install.sh: Python 3.9+ is required (python3 not found)." >&2
exit 1
