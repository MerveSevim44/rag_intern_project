"""
Madde 21 regresyon testleri — judge raporunda pozitif soruda ret (FN).

Judge yalnız bağlama baktığı için retrieval doğru chunk'ı getirmediğinde
reti "dürüst ret" diye ödüllendiriyor (AR=4, TP=4). Judge raporu bu satırları
benchmark'ın KENDİ sınıflandırmasıyla (classify_answer) ayrı saymalı.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "evaluation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluation.benchmark_eval import classify_answer  # noqa: E402
import llm_as_judge as lj  # noqa: E402

GT = {"1": {"referans_cevaplar": ["Gümüş Yaprak"]}}
RET = "Bu bilgi dokümanlarda bulunamadı."


def _row(cevap, beklenen="test1.txt", var_mi="Evet", soru_id="1"):
    return {"id": soru_id, "soru": "Alis'in çalıştığı kütüphanenin adı nedir?",
            "beklenen_kaynak": beklenen, "dokumanda_var_mi": var_mi, "cevap": cevap}


@pytest.mark.parametrize("row, beklenen", [
    (_row(RET), "FN"),
    (_row("Kütüphanenin adı Gümüş Yaprak'tır."), "TP"),
    (_row(RET, beklenen="-", var_mi="Hayır", soru_id="9"), "TN"),
    (_row("Kütüphanenin adı Gümüş Yaprak'tır.", beklenen="-", var_mi="Hayır", soru_id="9"), "FP"),
    # Etiket çelişkisi: bayrak Hayır ama kaynak + referans var -> pozitif sayılır
    (_row(RET, var_mi="Hayır"), "FN"),
    (_row("HATA: service_failure: code_interpreter"), "HATA"),
])
def test_classify_answer(row, beklenen):
    assert classify_answer(row, GT) == beklenen


def _judged(soru_id, sinif, ar, tp):
    return {"id": soru_id, "siniflandirma": sinif, "faithfulness_score": 5,
            "answer_relevance_score": ar, "task_performance_score": tp, "alignment_score": 5}


def test_ozet_fn_ve_odul_sayaci(capsys):
    results = [
        _judged("1", "TP", 5, 5),
        _judged("2", "FN", 4, 4),   # ödüllendirilmiş ret (retrieval kaçırması)
        _judged("3", "FN", 1, 1),   # judge doğru cezalandırmış (cevap bağlamdaydı)
        _judged("4", "TN", 4, 4),   # negatifte doğru ret: FN değil
    ]
    lj.print_summary(results)
    out = capsys.readouterr().out
    assert "Pozitif soruda ret (FN): 2" in out
    assert "ödüllendirdiği (AR>=4 ve TP>=4): 1 [2]" in out
    # answer_relevance: tüm ort (5+4+1+4)/4 = 3.50, FN hariç (5+4)/2 = 4.50
    line = next(l for l in out.splitlines() if l.startswith("answer_relevance_score"))
    assert "3.50" in line and line.rstrip().endswith("4.50")


def test_ozet_siniflandirma_yoksa_uyarir(capsys):
    lj.print_summary([{"id": "1", **{k: 5 for k in lj.SCORE_KEYS}}])
    out = capsys.readouterr().out
    assert "Pozitif soruda ret (FN): 0" in out
    assert "siniflandirma yok" in out
