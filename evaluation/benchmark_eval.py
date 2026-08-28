"""
benchmark_eval.py — Otomatik Doğruluk Skorlaması (Exact Match / F1) ve Benchmark Raporlama

Bu modül, test_sonuclari.csv dosyalarını otomatik olarak değerlendirir:
1. Türkçe Uyumlu Metin Normalizasyonu
2. Exact Match (EM) Skoru (Sıkı & Yumuşak)
3. Token Seviyesi Precision, Recall ve F1 Skoru (SQuAD standardı)
4. Retrieval (Kaynak Eşleşme) Başarısı
5. Negatif Test & Halüsinasyon Tespiti (TP, TN, FP, FN Sınıflandırması)
6. Yanıt Süresi (Latency) Analizi
7. Yüksek Kaliteli Benchmark Görselleri (PNG) Üretimi
8. CSV & JSON Rapor Dışa Aktarımı
"""

import argparse
import csv
import json
import re
import string
from collections import Counter
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Türkçe karakter dönüşüm haritası
TR_LOWER_MAP = {
    ord("İ"): "i",
    ord("I"): "ı",
    ord("Ö"): "ö",
    ord("Ü"): "ü",
    ord("Ş"): "ş",
    ord("Ç"): "ç",
    ord("Ğ"): "ğ",
}


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri güvenli şekilde küçük harfe çevirir."""
    if not text:
        return ""
    return text.translate(TR_LOWER_MAP).lower()


def normalize_text_tr(text: str) -> str:
    """
    Değerlendirme öncesi metni temizler ve standardize eder:
    - Küçük harfe çevirme (Türkçe uyumlu)
    - Kaynak satırlarını ("Kaynak: ...", "(sayfa 2)") ve sistem kalıntılarını ("ÜRETİMİ BİTİR.") temizleme
    - Noktalama işaretlerini boşluğa dönüştürme
    - Fazla boşlukları kaldırma
    """
    if not text:
        return ""

    text = turkish_lower(text)

    # Sistem ve kaynak kalıntılarını temizle
    text = re.sub(r"kaynak\s*:\s*.*", "", text)
    text = re.sub(r"üretimi\s+bitir\.?", "", text)
    text = re.sub(r"bu bilgi dokümanlarda bulunmuştur\.?", "", text)
    text = re.sub(r"adlı kaynaktan alındı\.?", "", text)
    text = re.sub(r"cevap\s*:\s*", "", text)

    # Noktalama işaretlerini kaldır
    punct_pattern = re.compile(f"[{re.escape(string.punctuation)}'\"’“”«»–—\n\r\t]")
    text = punct_pattern.sub(" ", text)

    # Tekrarlayan boşlukları teke indir
    text = " ".join(text.split())
    return text


def tokenize_tr(text: str) -> list[str]:
    """Normalize edilmiş metni kelime token'larına ayırır."""
    normalized = normalize_text_tr(text)
    return normalized.split()


def compute_exact_match(prediction: str, ground_truths: list[str]) -> float:
    """
    Exact Match (EM) Skoru (0.0 veya 1.0)
    Tahmin ile herhangi bir referans cevabın normalize hali birebir eşleşiyor mu?
    """
    norm_pred = normalize_text_tr(prediction)
    for gt in ground_truths:
        norm_gt = normalize_text_tr(gt)
        if norm_pred == norm_gt:
            return 1.0
        # Kısa yanıtlar için (örn "304", "alis", "korev", "sqlite", "dörtlü")
        if len(norm_gt.split()) <= 3 and norm_gt in norm_pred:
            # Eğer yanıt içinde doğrudan hedef net cevap geçiyorsa tam eşleşme kabul edilir
            return 1.0
    return 0.0


def compute_token_f1(prediction: str, ground_truths: list[str]) -> tuple[float, float, float]:
    """
    Token-Level F1 Skoru (Precision, Recall, F1)
    SQuAD / QA değerlendirme standardına uygun şekilde kelime çakışması üzerinden hesaplanır.
    """
    pred_tokens = tokenize_tr(prediction)
    if not pred_tokens:
        return 0.0, 0.0, 0.0

    best_f1 = 0.0
    best_prec = 0.0
    best_rec = 0.0

    for gt in ground_truths:
        gt_tokens = tokenize_tr(gt)
        if not gt_tokens:
            continue

        common = Counter(pred_tokens) & Counter(gt_tokens)
        num_same = sum(common.values())

        if num_same == 0:
            f1, prec, rec = 0.0, 0.0, 0.0
        else:
            prec = num_same / len(pred_tokens)
            rec = num_same / len(gt_tokens)
            f1 = (2 * prec * rec) / (prec + rec)

        if f1 > best_f1:
            best_f1 = f1
            best_prec = prec
            best_rec = rec

    return best_f1, best_prec, best_rec


def check_is_not_found(text: str) -> bool:
    """Modelin 'dokümanlarda bulunamadı' yanıtı verip vermediğini tespit eder."""
    norm = normalize_text_tr(text)
    patterns = [
        "dokumanlarda bulunamadi",
        "dokümanlarda bulunamadı",
        "bilgi dokumanlarda",
        "bulunamadi",
        "bulunmamaktadir",
        "bilgi yer almamaktadir",
        "metinde gecmemektedir",
    ]
    return any(p in norm for p in patterns)


def _is_negative_flag(value: str) -> bool:
    """'dokumanda_var_mi' sütununu Türkçe karakter farklarına dayanıklı okur.

    CSV'lerde bu alan 'Hayır', 'Hayir', 'hayır', 'no' gibi farklı biçimlerde
    yazılabiliyor; düz '== "Hayir"' karşılaştırması negatif soruların tamamını
    pozitif sayıp TN/FP matrisini bozuyordu.
    """
    norm = turkish_lower((value or "").strip())
    return norm in {"hayir", "hayır", "hayÄ±r", "no", "yok", "0", "false"}


def _resolve_file(file_path: str) -> Path:
    """Verilen dosya yolunu yerel, datasets ve root dizinlerinde arayarak çözer."""
    p = Path(file_path)
    if p.exists():
        return p
    eval_dir = Path(__file__).resolve().parent
    root_dir = eval_dir.parent
    candidates = [
        eval_dir / file_path,
        root_dir / file_path,
        eval_dir / "datasets" / file_path,
        eval_dir / "datasets" / p.name,
        eval_dir / p.name,
        root_dir / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return p


def evaluate_dataset(
    csv_path: str = "test_sonuclari.csv",
    ground_truth_path: str = "ground_truth.json",
    output_dir: str = "report",
) -> dict:
    """
    Sonuç CSV dosyasını okuyup ground_truth ile eşleştirerek tüm metrikleri hesaplar.
    """
    csv_file = _resolve_file(csv_path)
    gt_file = _resolve_file(ground_truth_path)
    
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        root_dir = Path(__file__).resolve().parent.parent
        out_dir = root_dir / output_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "benchmark_charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    if not csv_file.exists():
        raise FileNotFoundError(
            f"Sonuç dosyası bulunamadı: '{csv_path}'.\n"
            f"Benchmark skorlamasını yapabilmek için önce test sorularını LLM ile çalıştırıp sonuç dosyasını üretmelisiniz:\n"
            f"  → python run_tests.py evaluation/datasets/test.csv test_sonuclari.csv\n"
            f"Veya hazır bir sonuç CSV dosyanız varsa yolunu parametre olarak verin:\n"
            f"  → python benchmark_eval.py dosya_yolu.csv"
        )
    if not gt_file.exists():
        raise FileNotFoundError(
            f"Ground truth dosyası bulunamadı: '{ground_truth_path}'.\n"
            f"Referans cevapların bulunduğu ground_truth.json dosyasının varlığından emin olun."
        )

    with open(gt_file, "r", encoding="utf-8") as f:
        ground_truths = json.load(f)

    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        results = list(reader)

    scored_records = []
    category_stats = {
        "Kolay": {"total": 0, "scored": 0, "em": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Orta": {"total": 0, "scored": 0, "em": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Zor": {"total": 0, "scored": 0, "em": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Negatif": {"total": 0, "scored": 0, "em": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "retrieval_ok": 0, "latencies": []},
    }

    confusion = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}

    for row in results:
        q_id = str(row.get("id", "")).strip()
        difficulty = row.get("zorluk", "Orta").capitalize()
        question = row.get("soru", "")
        expected_src = row.get("beklenen_kaynak", "").strip()
        doc_exists = (row.get("dokumanda_var_mi") or "Evet").strip()
        doc_is_negative = _is_negative_flag(doc_exists)
        prediction = row.get("cevap", "")
        found_src = row.get("bulunan_kaynaklar", "")
        try:
            latency = float(row.get("sure_sn", 0.0))
        except (ValueError, TypeError):
            latency = 0.0

        gt_info = ground_truths.get(q_id, {})
        ref_answers = gt_info.get("referans_cevaplar", [])
        # Referans cevabı olmayan sorular EM/F1 ortalamasına KATILMAZ. Eskiden
        # tahminin kendisi referans kabul ediliyordu; bu her soruya EM=1.0
        # vererek skorları yapay olarak şişiriyordu.
        has_reference = bool(ref_answers)

        is_negative = doc_is_negative or (expected_src == "-")
        pred_is_not_found = check_is_not_found(prediction)

        # Retrieval kontrolü
        if is_negative:
            # Negatif sorularda kaynak aranmaz
            retrieval_match = True
        else:
            retrieval_match = (expected_src in found_src) if expected_src else False

        # Exact Match & F1
        if not has_reference and not is_negative:
            em_score = f1_score = prec_score = rec_score = 0.0
        elif is_negative:
            # Negatif soruda başarı: modelin bulunamadı demesi
            em_score = 1.0 if pred_is_not_found else 0.0
            f1_score = 1.0 if pred_is_not_found else 0.0
            prec_score = 1.0 if pred_is_not_found else 0.0
            rec_score = 1.0 if pred_is_not_found else 0.0
        else:
            em_score = compute_exact_match(prediction, ref_answers)
            f1_score, prec_score, rec_score = compute_token_f1(prediction, ref_answers)

        # Sınıflandırma Mantığı (TP, TN, FP, FN)
        if not is_negative:
            if pred_is_not_found:
                status = "FN"  # Yanlış Negatif (Dokümanda vardı ama bulamadı)
                confusion["FN"] += 1
            else:
                status = "TP"  # Doğru Pozitif (Dokümanda vardı ve yanıt üretti)
                confusion["TP"] += 1
        else:
            if pred_is_not_found:
                status = "TN"  # Doğru Negatif (Dokümanda yoktu ve başarıyla reddetti)
                confusion["TN"] += 1
            else:
                status = "FP"  # Yanlış Pozitif / Halüsinasyon (Dokümanda yoktu ama uydurdu)
                confusion["FP"] += 1

        # Kategori bazlı istatistikleri güncelle
        cat_key = "Negatif" if is_negative else difficulty
        if cat_key not in category_stats:
            cat_key = "Orta"

        scored_for_accuracy = has_reference or is_negative

        stats = category_stats[cat_key]
        stats["total"] += 1
        if scored_for_accuracy:
            stats["scored"] += 1
        stats["em"] += em_score
        stats["f1_sum"] += f1_score
        stats["p_sum"] += prec_score
        stats["r_sum"] += rec_score
        if retrieval_match:
            stats["retrieval_ok"] += 1
        stats["latencies"].append(latency)

        scored_records.append({
            "id": q_id,
            "zorluk": difficulty,
            "kategori": cat_key,
            "soru": question,
            "beklenen_kaynak": expected_src,
            "dokumanda_var_mi": doc_exists,
            "cevap": prediction,
            "referans_cevaplar": " | ".join(ref_answers),
            "em_score": round(em_score * 100, 1),
            "f1_score": round(f1_score * 100, 1),
            "precision": round(prec_score * 100, 1),
            "recall": round(rec_score * 100, 1),
            "retrieval_match": "Evet" if retrieval_match else "Hayır",
            "siniflandirma": status,
            "referans_var_mi": "Evet" if (has_reference or is_negative) else "Hayır",
            "sure_sn": latency,
        })

    # Genel Özet Hesaplama
    total_q = len(results)
    if not scored_records:
        raise ValueError(f"Sonuç dosyası boş veya okunamadı: {csv_file}")

    # EM/F1 yalnızca referans cevabı olan (veya negatif) sorular üzerinden
    # ortalanır; referanssız sorular paydaya girerse skor yapay olarak düşer.
    accuracy_pool = [r for r in scored_records if r["referans_var_mi"] == "Evet"]
    n_acc = len(accuracy_pool)
    overall_em = sum(r["em_score"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_f1 = sum(r["f1_score"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_prec = sum(r["precision"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_rec = sum(r["recall"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_retrieval = sum(1 for r in scored_records if r["retrieval_match"] == "Evet") / total_q * 100 if total_q else 0.0
    all_latencies = [r["sure_sn"] for r in scored_records]

    category_summary = {}
    for cat, data in category_stats.items():
        cnt = data["total"]
        acc_cnt = data["scored"] or cnt
        if cnt > 0:
            category_summary[cat] = {
                "toplam_soru": cnt,
                "referansli_soru": data["scored"],
                "exact_match_yuzde": round((data["em"] / acc_cnt) * 100, 2),
                "f1_skor_yuzde": round((data["f1_sum"] / acc_cnt) * 100, 2),
                "precision_yuzde": round((data["p_sum"] / acc_cnt) * 100, 2),
                "recall_yuzde": round((data["r_sum"] / acc_cnt) * 100, 2),
                "retrieval_dogruluk_yuzde": round((data["retrieval_ok"] / cnt) * 100, 2),
                "ortalama_sure_sn": round(np.mean(data["latencies"]), 2) if data["latencies"] else 0.0,
                "medyan_sure_sn": round(float(np.median(data["latencies"])), 2) if data["latencies"] else 0.0,
                "min_sure_sn": round(min(data["latencies"]), 2) if data["latencies"] else 0.0,
                "max_sure_sn": round(max(data["latencies"]), 2) if data["latencies"] else 0.0,
            }

    summary = {
        "toplam_soru": total_q,
        "referansli_soru": n_acc,
        "referanssiz_soru": total_q - n_acc,
        "genel_metrikler": {
            "exact_match_yuzde": round(overall_em, 2),
            "f1_skor_yuzde": round(overall_f1, 2),
            "precision_yuzde": round(overall_prec, 2),
            "recall_yuzde": round(overall_rec, 2),
            "retrieval_dogruluk_yuzde": round(overall_retrieval, 2),
            "ortalama_sure_sn": round(float(np.mean(all_latencies)), 2) if all_latencies else 0.0,
            "medyan_sure_sn": round(float(np.median(all_latencies)), 2) if all_latencies else 0.0,
            "min_sure_sn": round(min(all_latencies), 2) if all_latencies else 0.0,
            "max_sure_sn": round(max(all_latencies), 2) if all_latencies else 0.0,
        },
        "siniflandirma_matrisi": confusion,
        "kategori_bazli": category_summary,
    }

    # CSV Dışa Aktarım
    scored_csv_path = out_dir / "test_sonuclari_scored.csv"
    fieldnames = list(scored_records[0].keys())
    with open(scored_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored_records)

    # JSON Dışa Aktarım
    summary_json_path = out_dir / "benchmark_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Grafikleri Üret
    generate_benchmark_charts(summary, scored_records, charts_dir)

    print("\n" + "=" * 80)
    print("🎯 OTOMATİK SKORLAMA & BENCHMARK SONUÇLARI")
    print("=" * 80)
    print(f"Toplam Değerlendirilen Soru : {total_q}")
    print(f"Genel Exact Match (EM)      : %{summary['genel_metrikler']['exact_match_yuzde']:.1f}")
    print(f"Genel Token F1 Skoru        : %{summary['genel_metrikler']['f1_skor_yuzde']:.1f}")
    print(f"Retrieval Kaynak Doğruluğu  : %{summary['genel_metrikler']['retrieval_dogruluk_yuzde']:.1f}")
    print(f"Ortalama Yanıt Süresi       : {summary['genel_metrikler']['ortalama_sure_sn']:.2f} sn")
    print(f"Halüsinasyon (FP) Oranı     : {confusion['FP']} / {total_q} (%{(confusion['FP'] / total_q) * 100 if total_q else 0.0:.1f})")
    if total_q - n_acc:
        print(f"⚠️  Referans cevabı olmayan {total_q - n_acc} soru EM/F1 ortalamasına dahil edilmedi "
              f"(ground_truth.json'a ekleyin).")
    print("-" * 80)
    print("📊 Kategori Bazlı Dağılım:")
    for cat, m in category_summary.items():
        print(f"  [{cat:8s}] EM: %{m['exact_match_yuzde']:5.1f} | F1: %{m['f1_skor_yuzde']:5.1f} | Kaynak: %{m['retrieval_dogruluk_yuzde']:5.1f} | Süre: {m['ortalama_sure_sn']:4.1f}s")
    print("=" * 80)
    print(f"📁 Kaydedilen Dosyalar:")
    print(f"  - Scored CSV   : {scored_csv_path}")
    print(f"  - Summary JSON : {summary_json_path}")
    print(f"  - Grafikler    : {charts_dir}")

    return summary


def generate_benchmark_charts(summary: dict, scored_records: list[dict], output_dir: Path):
    """
    Modern, profesyonel kalitede 3 adet benchmark grafiği üretir ve kaydeder.
    """
    # Genel stil yapılandırması
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial", "Helvetica"]
    plt.rcParams["axes.edgecolor"] = "#CBD5E1"
    plt.rcParams["axes.linewidth"] = 0.8

    categories = ["Kolay", "Orta", "Zor", "Negatif"]
    cat_summary = summary["kategori_bazli"]

    # -------------------------------------------------------------
    # Grafik 1: Doğruluk & F1 Skoru (Kategori & Genel Karşılaştırma)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    x_labels = [f"{c}\n(n={cat_summary.get(c, {}).get('toplam_soru', 0)})" for c in categories] + [
        f"GENEL\n(n={summary['toplam_soru']})"
    ]
    x = np.arange(len(x_labels))
    width = 0.26

    em_values = [cat_summary.get(c, {}).get("exact_match_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["exact_match_yuzde"]
    ]
    f1_values = [cat_summary.get(c, {}).get("f1_skor_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["f1_skor_yuzde"]
    ]
    retrieval_values = [cat_summary.get(c, {}).get("retrieval_dogruluk_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["retrieval_dogruluk_yuzde"]
    ]

    rects1 = ax.bar(x - width, em_values, width, label="Exact Match (EM %)", color="#3B82F6", edgecolor="#1D4ED8", alpha=0.9, zorder=3)
    rects2 = ax.bar(x, f1_values, width, label="Token F1 Skoru (%)", color="#10B981", edgecolor="#047857", alpha=0.9, zorder=3)
    rects3 = ax.bar(x + width, retrieval_values, width, label="Retrieval Doğruluğu (%)", color="#F59E0B", edgecolor="#B45309", alpha=0.9, zorder=3)

    # Değer etiketleri
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax.annotate(
                    f"%{height:.1f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    fontweight="bold",
                    color="#1E293B",
                )

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    ax.set_ylabel("Başarı Oranı (%)", fontsize=11, fontweight="bold", color="#1E293B")
    ax.set_title("RAG Sistemi Soru Zorluğuna Göre Doğruluk & F1 Karşılaştırması", fontsize=13, fontweight="bold", pad=15, color="#0F172A")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=10, fontweight="bold", color="#334155")
    ax.set_ylim(0, 115)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="lower right", fontsize=9.5)

    plt.tight_layout()
    chart1_path = output_dir / "benchmark_accuracy_f1.png"
    plt.savefig(chart1_path, dpi=300)
    plt.close()

    # -------------------------------------------------------------
    # Grafik 2: Yanıt Süresi (Latency) Dağılımı ve Ortalamaları
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300, gridspec_kw={"width_ratios": [1.4, 1]})
    fig.patch.set_facecolor("#FFFFFF")
    ax1.set_facecolor("#F8FAFC")
    ax2.set_facecolor("#F8FAFC")

    # Kategori bazlı süre bar grafiği
    cat_names = categories + ["Genel"]
    avg_times = [cat_summary.get(c, {}).get("ortalama_sure_sn", 0.0) for c in categories] + [summary["genel_metrikler"]["ortalama_sure_sn"]]
    med_times = [cat_summary.get(c, {}).get("medyan_sure_sn", 0.0) for c in categories] + [summary["genel_metrikler"]["medyan_sure_sn"]]

    x_idx = np.arange(len(cat_names))
    b_width = 0.35

    ax1.bar(x_idx - b_width/2, avg_times, b_width, label="Ortalama Süre (sn)", color="#6366F1", edgecolor="#4338CA", alpha=0.9, zorder=3)
    ax1.bar(x_idx + b_width/2, med_times, b_width, label="Medyan Süre (sn)", color="#EC4899", edgecolor="#BE185D", alpha=0.9, zorder=3)

    for i, (avg_v, med_v) in enumerate(zip(avg_times, med_times)):
        ax1.text(i - b_width/2, avg_v + 0.6, f"{avg_v:.1f}s", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E293B")
        ax1.text(i + b_width/2, med_v + 0.6, f"{med_v:.1f}s", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E293B")

    ax1.set_title("Kategori Bazında Yanıt Süreleri (Latency)", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax1.set_ylabel("Süre (Saniye)", fontsize=10, fontweight="bold", color="#1E293B")
    ax1.set_xticks(x_idx)
    ax1.set_xticklabels(cat_names, fontsize=9.5, fontweight="bold", color="#334155")
    ax1.set_ylim(0, (max(avg_times + med_times) or 1.0) * 1.25)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax1.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="upper left", fontsize=8.5)

    # Süre dağılımı (Histogram / Boxplot)
    all_lat = [r["sure_sn"] for r in scored_records] or [0.0]
    ax2.hist(all_lat, bins=8, color="#0EA5E9", edgecolor="#0284C7", alpha=0.85, zorder=3)
    ax2.axvline(np.mean(all_lat), color="#DC2626", linestyle="--", linewidth=1.5, label=f"Ortalama: {np.mean(all_lat):.1f}s", zorder=4)
    ax2.axvline(float(np.median(all_lat)), color="#16A34A", linestyle=":", linewidth=2, label=f"Medyan: {np.median(all_lat):.1f}s", zorder=4)

    ax2.set_title("Tüm Test Sorularının Süre Dağılımı", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax2.set_xlabel("Yanıt Süresi (Saniye)", fontsize=10, fontweight="bold", color="#1E293B")
    ax2.set_ylabel("Soru Frekansı", fontsize=10, fontweight="bold", color="#1E293B")
    ax2.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax2.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="upper right", fontsize=8.5)

    plt.tight_layout()
    chart2_path = output_dir / "benchmark_latency.png"
    plt.savefig(chart2_path, dpi=300)
    plt.close()

    # -------------------------------------------------------------
    # Grafik 3: Genel Sistem Başarı Karnesi & Sınıflandırma Matrisi
    # -------------------------------------------------------------
    fig, (ax_donut, ax_card) = plt.subplots(1, 2, figsize=(11, 5), dpi=300, gridspec_kw={"width_ratios": [1, 1.2]})
    fig.patch.set_facecolor("#FFFFFF")
    ax_donut.set_facecolor("#FFFFFF")
    ax_card.set_facecolor("#F8FAFC")

    # Donut Chart - Sınıflandırma
    conf = summary["siniflandirma_matrisi"]
    labels = ["Doğru Pozitif (TP)", "Doğru Negatif (TN)", "Yanlış Negatif (FN)", "Halüsinasyon (FP)"]
    sizes = [conf["TP"], conf["TN"], conf["FN"], conf["FP"]]
    colors = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444"]
    explode = (0.03, 0.03, 0.05, 0.08)

    if sum(sizes) == 0:
        sizes = [1, 0, 0, 0]

    wedges, texts, autotexts = ax_donut.pie(
        sizes,
        explode=explode,
        labels=None,
        colors=colors,
        autopct=lambda p: f"{p:.1f}%\n({int(round(p * sum(sizes) / 100))})" if p > 0 else "",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor="#FFFFFF", linewidth=2),
    )
    for at in autotexts:
        at.set_color("#0F172A")
        at.set_fontsize(8.5)
        at.set_fontweight("bold")

    ax_donut.set_title("Test Sınıflandırma Dağılımı\n(Toplam 30 Soru)", fontsize=11.5, fontweight="bold", pad=10, color="#0F172A")
    ax_donut.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8, frameon=False)

    # KPI Kartları
    ax_card.axis("off")
    kpis = [
        ("Exact Match (EM)", f"%{summary['genel_metrikler']['exact_match_yuzde']:.1f}", "#3B82F6"),
        ("Token F1 Skoru", f"%{summary['genel_metrikler']['f1_skor_yuzde']:.1f}", "#10B981"),
        ("Retrieval Başarısı", f"%{summary['genel_metrikler']['retrieval_dogruluk_yuzde']:.1f}", "#F59E0B"),
        ("Negatif Test Başarısı", f"%{(conf['TN'] / (conf['TN'] + conf['FP'])) * 100 if (conf['TN'] + conf['FP']) else 0.0:.1f}", "#8B5CF6"),
        ("Halüsinasyon Oranı", f"%{(conf['FP'] / summary['toplam_soru']) * 100 if summary['toplam_soru'] else 0.0:.1f}", "#EF4444"),
        ("Ortalama Yanıt Süresi", f"{summary['genel_metrikler']['ortalama_sure_sn']:.2f} sn", "#6366F1"),
    ]

    ax_card.text(0.5, 0.98, "Sistem Başarı Karnesi (KPI Özeti)", ha="center", va="top", fontsize=12, fontweight="bold", color="#0F172A")

    for i, (title, val, col) in enumerate(kpis):
        y_pos = 0.82 - (i * 0.14)
        # Kutu arka planı
        rect = plt.Rectangle((0.05, y_pos - 0.04), 0.9, 0.11, facecolor="#FFFFFF", edgecolor=col, linewidth=1.5, transform=ax_card.transAxes, zorder=2, clip_on=False)
        ax_card.add_patch(rect)
        ax_card.text(0.1, y_pos + 0.015, title, fontsize=9.5, fontweight="bold", color="#334155", transform=ax_card.transAxes, zorder=3)
        ax_card.text(0.88, y_pos + 0.015, val, fontsize=11, fontweight="bold", color=col, ha="right", transform=ax_card.transAxes, zorder=3)

    plt.tight_layout()
    chart3_path = output_dir / "benchmark_overall_summary.png"
    plt.savefig(chart3_path, dpi=300)
    plt.close()


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="RAG test sonuçlarını otomatik skorlar ve benchmark grafikleri üretir.")
    parser.add_argument("sonuclar_csv", nargs="?", default="test_sonuclari.csv", help="Skorlanacak sonuç CSV dosyası")
    parser.add_argument("ground_truth", nargs="?", default="ground_truth.json", help="Ground Truth referans JSON dosyası")
    parser.add_argument("--output-dir", default="report", help="Rapor ve grafiklerin kaydedileceği dizin")

    args = parser.parse_args()
    try:
        evaluate_dataset(args.sonuclar_csv, args.ground_truth, args.output_dir)
    except FileNotFoundError as e:
        sys.exit(f"\n[HATA] {e}\n")
    except Exception as e:
        sys.exit(f"\n[HATA] Değerlendirme sırasında bir hata oluştu: {e}\n")
