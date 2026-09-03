#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$LOCAL_DIR/scripts/local" up all
