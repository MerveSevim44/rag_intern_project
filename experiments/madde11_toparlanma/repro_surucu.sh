#!/bin/bash
# Kökten çalıştırılır: FOUNDRY_LOCAL_ENDPOINT=http://127.0.0.1:PORT bash experiments/madde11_toparlanma/repro_surucu.sh
# Her adım ayrı süreç, 90 sn sert zaman aşımı (asılırsa kill edilir, TEKRAR DENENMEZ, sürücü durur).
D=experiments/madde11_toparlanma; OUT=$D/repro.jsonl; : > "$OUT"
export PYTHONIOENCODING=utf-8
adim() {  # adim MOD [BOYUT]
  timeout 90 python -u $D/repro.py "$@" "$OUT" </dev/null > /dev/null 2>>$D/repro_hata.log
  local k=$?
  echo "{\"adim_cikis\": \"$*\", \"cikis\": $k}" >> "$OUT"
  [ $k -eq 0 ] || { echo "ADIM BASARISIZ/ZAMAN ASIMI: $* (cikis=$k)"; exit $k; }
}
: > $D/repro_hata.log
adim snap
adim wear
adim wear
for b in 12600 15000 12600 15000 15000 18000; do
  adim cycle $b
  if tail -2 "$OUT" | grep -q '"BOZUK": true'; then echo "BOZULMA BULUNDU ($b)"; adim tier2; adim snap; exit 0; fi
done
echo "BOZULMA URETILEMEDI"; adim snap
