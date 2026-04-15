#!/bin/bash
# Run QEMU flow tests with the new Python UI.
#
# Usage:
#   ./tools/run_with_new_ui.sh tests/flows/backlight/test_backlight.sh
#   ./tools/run_with_new_ui.sh tests/test_all_flows.sh
#
# Results go to: tests/flows/_results/current/{flow}/...
# Original .so results go to: tests/flows/_results/original/{flow}/...
# The target is baked into the path by common.sh — no manual override needed.

set -euo pipefail
export TEST_TARGET=current
exec "$@"
