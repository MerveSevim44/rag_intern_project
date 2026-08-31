# Koken notu — negatif set

`report/` ve `results/` (100 soru) bu deneye, yani trim duzeltmesi sonrasi
baseline'a aittir (commit e5287b5, F1 38.8 / FN 25).

`results/test_negative_sonuclari.csv` ise BU kosudan degil, bir onceki
kosudan (archive/reports_old/results_after_pre_trim/) kopyalanmistir —
report_final_v2 ile eslesen bir negatif set kosusu hic yapilmamisti.
Negatif set commit 73f2055'te eklendi ve trim duzeltmesi ret davranisini
degistirmediginden (25/25 vakada trim_changed=False) bu deger v2 icin
gecerli bir baseline kabul edildi: FP 7/32.

Bu, birebir eslesen bir olcum degil; kesin karsilastirma gerekiyorsa
negatif set v2 kodu ile yeniden kosulmalidir.
