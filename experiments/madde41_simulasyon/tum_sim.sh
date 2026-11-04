#!/bin/bash
cd "$(dirname "$0")/../.."
for s in test_negative test_2; do
  echo "=== $(date) BASLIYOR: $s ==="
  python -u experiments/madde41_simulasyon/kosu_sim.py "$s" || echo "!!! $s hata ile bitti ($?)"
  echo "=== $(date) BITTI: $s ==="
done
echo "=== TUM SIM TAMAMLANDI ==="
