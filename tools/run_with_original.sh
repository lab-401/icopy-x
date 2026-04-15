#!/bin/bash
# Run QEMU flow tests with the original .so modules (baseline).
#
# Usage:
#   ./tools/run_with_original.sh tests/flows/backlight/test_backlight.sh
#
# Results go to: tests/flows/_results/original/{flow}/...
# This is the default when TEST_TARGET is unset, but using this script
# makes the intent explicit.

set -euo pipefail
export TEST_TARGET=original
exec "$@"
