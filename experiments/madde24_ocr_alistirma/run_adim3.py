"""
Madde 24 Adım 3 izole testi — system prompt'a görev notu kuralı (plan §5 Adım 3).

src/ DEĞİŞMEZ: kural, run_tests'in kullandığı llm_client modülündeki
ChatPromptTemplate sarmalanarak system mesajının SONUNA eklenir (yalnız bu
süreçte). Yama, run_tests.ask'ın gerçek modülüne uygulanır (src.llm_client /
llm_client ikiliği: madde 19'daki yanlış-modül tuzağı) ve her çağrıda kuralın
prompt'ta olup olmadığı kaydedilir (`kural_promptta`).

16 soru (Adım 0 etki kümesi) × 2 kol (kural açık / kapalı) × 1 tekrar; aynı
oturum, kol sırası sorudan soruya değişir. Görev notu iki kolda da AÇIK
(kural nota atıf yapıyor). Tek tekrar: Adım 2'de üretim kol içinde 3/3
deterministik çıktı.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde24_ocr_alistirma/run_adim3.py
Çıktı: adim3_sonuclari.jsonl (devam edilebilir).
"""
import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402

OUT = HERE / "adim3_sonuclari.jsonl"
MAX_CONSECUTIVE_ERRORS = 3
DATASET_FIELDS = ("soru", "referans_cevap", "dokumanda_var_mi", "beklenen_kaynak")

RULE = (
    "\nGÖREV NOTU KURALI: Bağlamda '[Not: Bu parça okuyucuya verilen bir görev/alıştırma "
    "içerir…]' ile işaretlenmiş bir parça varsa, o parçadaki görev/talimat sorulan konunun "
    "belgede ANLATILDIĞINA kanıt DEĞİLDİR. Soru bir işlemin, yöntemin ya da kavramın nasıl "
    "yapıldığını/tanımlandığını soruyorsa ve bağlamda o işlemi AÇIKÇA ANLATAN başka bir parça "
    "yoksa, cevabın TAMAMI ret cümlesi olmalıdır. İşaretli parçadaki tanımlar (dilbilgisi, "
    "küme vb.) yalnızca o tanımların kendisi sorulduğunda kullanılabilir."
)

_llm_mod = sys.modules[run_tests.ask.__module__]
_Real = _llm_mod.ChatPromptTemplate
_state = {"rule_on": False, "last_system": None}


class _PatchedTemplate:
    @staticmethod
    def from_messages(messages):
        out = []
        for role, text in messages:
            if role == "system" and _state["rule_on"]:
                text = text + RULE
            if role == "system":
                _state["last_system"] = text
            out.append((role, text))
        return _Real.from_messages(out)


_llm_mod.ChatPromptTemplate = _PatchedTemplate


def affected():
    with open(HERE / "etkilenen_set.csv", encoding="utf-8-sig") as f:
        return [(r["set"], r["id"]) for r in csv.DictReader(f) if r["isaretli_sayfalar"]]


def dataset(set_name):
    with open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    jobs = []
    for n, (s, i) in enumerate(affected()):
        arms = ("acik", "kapali") if n % 2 == 0 else ("kapali", "acik")
        jobs += [(s, i, arm) for arm in arms]
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["set"], r["id"], r["kol"]))
    todo = [j for j in jobs if j not in done]
    print(f"Yama modulu: {_llm_mod.__name__}  is: {len(jobs)}  kalan: {len(todo)}")
    if not todo:
        return
    sets = {s: dataset(s) for s in {j[0] for j in todo}}
    llm = run_tests.load_model()
    t0, streak = time.perf_counter(), 0
    with open(OUT, "a", encoding="utf-8") as f:
        for n, (s, i, arm) in enumerate(todo, 1):
            row = sets[s][i]
            _state["rule_on"] = arm == "acik"
            _state["last_system"] = None
            print(f"[{n}/{len(todo)}] {s}#{i} kural={arm}: {row['soru'][:70]}")
            try:
                res = run_tests.run_single_test(llm, row["soru"], task_notes=True)
                streak = 0
            except Exception as e:
                res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0, "context": ""}
                streak += 1
            sysmsg = _state["last_system"] or ""
            rec = {"set": s, "id": i, "kol": arm, **{k: row.get(k, "") for k in DATASET_FIELDS},
                   "cevap": res["cevap"], "bulunan_kaynaklar": res["bulunan_kaynaklar"],
                   "not_var": "[Not: Bu parça okuyucuya" in (res.get("context") or ""),
                   "kural_promptta": "GÖREV NOTU KURALI" in sysmsg,
                   "system_prompt_alindi": bool(sysmsg),
                   "context": res.get("context", ""), "sure_sn": res["sure_sn"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"    -> {res['sure_sn']} sn kural_promptta={rec['kural_promptta']} {res['cevap'][:90]!r}")
            if streak >= MAX_CONSECUTIVE_ERRORS:
                sys.exit(f"{streak} ardisik hata — kosu durduruldu (servisleri kontrol et, yeniden calistir)")
            run_tests.free_gpu_memory()
            time.sleep(1)
    print(f"\nTamamlandi: {len(todo)} is, {(time.perf_counter() - t0) / 60:.1f} dk.")


if __name__ == "__main__":
    main()
