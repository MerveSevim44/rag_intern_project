#!/bin/bash
# HEAD üzerinde madde 39 gibi tam koşu: 6 set sıralı, sonuçlar head_<set> klasörlerine (referansa dokunmaz).
cd /c/Users/merve/Desktop/rag_project
export PYTHONIOENCODING=utf-8
for s in test_1 test_2 test_3 test_4 test_5 test_negative; do
  echo "[$(date +%H:%M:%S)] BASLA $s"
  python -u experiments/madde39_tam_kosu/kosu.py $s --klasor head_$s > "experiments/madde39_tam_kosu/head_$s.log" 2>&1 </dev/null
  k=$?
  echo "[$(date +%H:%M:%S)] BITTI $s cikis=$k"
done
echo "[$(date +%H:%M:%S)] TUM_SETLER_BITTI"
