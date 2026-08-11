#!/usr/bin/env bash
# Build reference-b2b-demo.zip for Knowledge Pack import (M5-1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/delivery/reference-b2b-demo.zip"
cd "${ROOT}/delivery/reference-pack"
rm -f "$OUT"
zip -r "$OUT" knowledge_pack.json files/
echo "Created $OUT"
