#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
for s in test_1 test_2 test_3 test_4 test_5 test_negative; do
  echo "=== $(date) BASLIYOR: $s ==="
  python -u experiments/madde30_sikilastirma/kosu.py "$s"
  echo "=== $(date) BITTI: $s ==="
done
echo "=== TUM KOSU TAMAMLANDI ==="
