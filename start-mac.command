#!/bin/sh
# Double-click to run Agentic QE Platform. Needs Python 3.12+, Node.js 20+, and Git.
cd "$(dirname "$0")" || exit 1
exec python3 scripts/dev.py up
