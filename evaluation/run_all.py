"""
run_all.py — test_1..test_4 setlerinin tamamını uçtan uca çalıştırır ve
hepsinin toplamından GENEL bir değerlendirme üretir.

Akış:
  1. (opsiyonel) Retrieval/yönlendirme değerlendirmesi  → eval_retrieval.evaluate_all
  2. Her set için LLM cevaplarını üret                  → run_tests.main
                                                          <set>_sonuclari.csv
  3. Her seti skorla + hepsinin birleşimini raporla     → benchmark_eval.evaluate_all
                                                          report/genel_summary.json

Kullanım:
  python evaluation/run_all.py                  # retrieval + LLM + benchmark (tam akış)
  python evaluation/run_all.py --only-retrieval # sadece retrieval (LLM gerekmez, hızlı)
  python evaluation/run_all.py --skip-llm       # cevaplar hazırsa sadece skorlama
  python evaluation/run_all.py --sets test_2 test_4
"""
import argparse
import sys
import time
from pathlib import Path

_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
# Sira onemli: insert(0) her adimda basa ekledigi icin listenin SONU
# sys.path'in BASINA gelir. evaluation/ en sonda ki kokteki ince wrapper'lar
# yerine asil moduller import edilsin.
for _p in [str(_root_dir), str(_root_dir / "src"), str(_eval_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

TEST_SETS = ["test_1", "test_2", "test_3", "test_4", "test_5"]


def result_path(set_name: str, results_dir: Path) -> Path:
    return results_dir / f"{set_name}_sonuclari.csv"


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Tüm test setlerini çalıştırır ve genel rapor üretir.")
    parser.add_argument("--sets", nargs="+", default=TEST_SETS, help="Çalıştırılacak setler")
    parser.add_argument("--skip-retrieval", action="store_true", help="Retrieval değerlendirmesini atla")
    parser.add_argument("--skip-llm", action="store_true",
                        help="LLM çalıştırmayı atla (mevcut <set>_sonuclari.csv dosyalarını skorla)")
    parser.add_argument("--only-retrieval", action="store_true",
                        help="Sadece retrieval/yönlendirme değerlendirmesi yap, LLM ve skorlamayı atla")
    parser.add_argument("--results-dir", default=".", help="Sonuç CSV'lerinin yazılacağı dizin")
    parser.add_argument("--output-dir", default="report", help="Rapor/grafik dizini")
    parser.add_argument("--force", action="store_true",
                        help="Sonuç CSV'si zaten varsa bile testi yeniden çalıştır")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = _root_dir / results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.perf_counter()

    # 1) Retrieval & yönlendirme
    if not args.skip_retrieval:
        import eval_retrieval
        print("\n" + "#" * 85)
        print("# ADIM 1/3 — RETRIEVAL & YÖNLENDİRME DEĞERLENDİRMESİ")
        print("#" * 85)
        eval_retrieval.evaluate_all(args.sets)

    if args.only_retrieval:
        print(f"\nToplam süre: {time.perf_counter() - t_start:.1f} sn")
        return 0

    # 2) LLM cevapları
    if not args.skip_llm:
        import run_tests
        print("\n" + "#" * 85)
        print("# ADIM 2/3 — LLM CEVAPLARININ ÜRETİLMESİ")
        print("#" * 85)
        for name in args.sets:
            out = result_path(name, results_dir)
            if out.exists() and not args.force:
                print(f"\n[{name}] Sonuç dosyası zaten var, atlanıyor: {out} (--force ile yeniden çalıştırın)")
                continue
            print(f"\n[{name}] Çalıştırılıyor → {out}")
            # Her set ayrı bir main() çağrısı: bir set çökse bile diğerleri sürer.
            try:
                run_tests.main([f"evaluation/datasets/{name}.csv", str(out)])
            except SystemExit as e:
                print(f"[{name}] Atlandı: {e}")
            except Exception as e:
                print(f"[{name}] HATA: {e}")

    # 3) Skorlama + genel değerlendirme
    import benchmark_eval
    print("\n" + "#" * 85)
    print("# ADIM 3/3 — SKORLAMA & GENEL DEĞERLENDİRME")
    print("#" * 85)
    try:
        benchmark_eval.evaluate_all(args.sets, args.output_dir, str(results_dir))
    except FileNotFoundError as e:
        print(f"\n[HATA] {e}")
        return 1

    print(f"\nToplam süre: {time.perf_counter() - t_start:.1f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
