"""
Madde 18 Adım 1 — 4 vakada (#44, #51, #57, #107) doğrulayıcının HAM yanıtı.

_semantic_check yalnız "SORUN" ile başlayan yanıtı itiraz sayıyor, geri kalanı
atıyor; yani şimdiye kadar "neden TAMAM dedi" hiç görülmedi. Burada gerçek
_semantic_check prompt'u (src'den, değiştirilmeden) 4 vakanın kayıtlı
soru/kod/sonuç üçlüsüyle kurulur ve LLM'in döndürdüğü metin olduğu gibi kaydedilir.
Kod ve sonuç: experiments/validator_A/results/log_gecis_1.txt (cevap bayt bayt
aynı çıkan 3 koşudan biri).

  V0  bugünkü prompt, 3 tekrar (temperature=0 mı, kararlı mı)
  VN  V0'dan "Emin degilsen TAMAM yaz." cümlesi çıkarılmış (3 tekrar)
  VNE VN + gerekçe-önce (2 tekrar)
  VE  aynı prompt + "önce 1-2 cümle gerekçe yaz, sonra TAMAM/SORUN" (tanı amaçlı,
      ürün promptu DEĞİL): modelin hatayı görüp görmediğini ayırır
      (görüyor ama "emin değilim" diyor mu, hiç görmüyor mu).

Kullanım (kökten): python -u experiments/madde18_dogrulayici/adim1_ham_yanit.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

VAKALAR = {
    "44": dict(
        soru="appointmentSettings içindeki minimumNoticeHours ile cancellationNoticeHours kavramsal olarak birbirinden nasıl ayrılmaktadır?",
        kod="""# minimumNoticeHours ve cancellationNoticeHours arasındaki farkı hesaplayalım
result = df.assign(
    notice_diff=lambda x: x['appointmentSettings.minimumNoticeHours'] - x['appointmentSettings.cancellationNoticeHours']
)

# minimumNoticeHours ve cancellationNoticeHours farklarının ağırlıklı ortalamasını hesaplayalım
average_diff = result['notice_diff'].mean()

# minimumNoticeHours ve cancellationNoticeHours farklarının ağırlıklı standart sapmasını hesaplayalım
std_diff = result['notice_diff'].std()

# sonuçları sözlük olarak döndürelim
result = {
    "ortalama fark": average_diff,
    "standart sapma": std_diff
}""",
        sonuc="{'ortalama fark': np.float64(-1.9478021978021978), 'standart sapma': np.float64(10.903226714928662)}"),
    "51": dict(
        soru="sectorDistribution içindeki 22 sektörün profil sayılarını gösteren bir grafik oluşturduğunuzda toplamın statistics.profileCount değeri olan 728'e eşit olup olmadığı nasıl doğrulanır?",
        kod="""# Sektorlerin sayısını hesapla
sector_counts = df['sector'].value_counts()

# Sektor sayısını toplam profildeki sayıyla karşılaştır
total_profiles = df.shape[0]

# Eşitlik kontrolü
result = {
    'sectors': sector_counts.to_dict(),
    'total_profiles': total_profiles,
    'is_equal': sector_counts.sum() == total_profiles
}""",
        sonuc="{'sectors': {'Sağlık': 40, 'Spor ve Fitness': 40, 'Eğitim ve Özel Ders': 40, 'Fizyoterapi ve Rehabilitasyon': 32, 'Psikoloji ve Danışmanlık': 32, 'Ağız ve Diş Sağlığı': 32, 'Güzellik ve Kişisel Bakım': 32, 'Beslenme ve Sağlıklı Yaşam': 32, 'Kuaför ve Berber': 32, 'Dil Eğitimi': 32, 'Sanat ve Hobi': 32, 'Teknoloji ve Yazılım': 32, 'Kreatif ve Tasarım': 32, 'İş ve Kariyer': 32, 'Hukuk ve Mali Hizmetler': 32, 'Teknik Servis ve Bakım': 32, 'Ev ve Yerinde Hizmet': 32, 'Otomotiv': 32, 'Evcil Hayvan Hizmetleri': 32, 'Etkinlik ve Organizasyon': 32, 'Kamu ve STK': 32, 'İşe Alım ve Görüşme': 32}, 'total_profiles': 728, 'is_equal': np.True_}"),
    "57": dict(
        soru="728 profil içinde her sektördeki ortalama meslek (occupation) sayısını bir grafikle gösterdiğinizde, occupationCount/sectorCount oranı sektörler arasında nasıl bir dağılım gösterir?",
        kod="""# Occupation sayısını sector bazında gruplandır ve ortalama hesapla
occupation_count_by_sector = df.groupby('sector')['occupation'].count().mean()

# Sector count'ları toplam olarak hesapla
total_sectors = df['sector'].nunique()

# occupationCount/sectorCount oranı hesapla
occupation_to_sector_ratio = occupation_count_by_sector / total_sectors

# Sonuçları bir sözlüğe at
result = {
    'Ortalama Meslek Sayısı': occupation_count_by_sector,
    'Toplam Sektor Sayısı': total_sectors,
    'occupationCount/sectorCount Oranı': occupation_to_sector_ratio
}""",
        sonuc="{'Ortalama Meslek Sayısı': np.float64(33.09090909090909), 'Toplam Sektor Sayısı': 22, 'occupationCount/sectorCount Oranı': np.float64(1.5041322314049588)}"),
    "107": dict(
        soru="728_profiles.json veri setinde profillerin ortalama randevu ücreti kaç TL'dir?",
        kod="result = df['appointmentSettings.defaultDurationMinutes'].mean()",
        sonuc="45.11675824175824"),
}

EK_EXPLAIN = ("\n\n[TANI] Cevap vermeden once 1-2 cumleyle gerekcesini yaz "
              "(soru ne istiyor, kod ne yapiyor, uyusuyor mu), sonra son satira "
              "TAMAM veya SORUN: <tek cumle> yaz.")


VARYANTLAR = [("V0", 3), ("VE", 2)]
if len(sys.argv) > 1:
    VARYANTLAR = [(v, 3 if v in ("V0", "VN") else 2) for v in sys.argv[1:]]
ADI = "adim1_ham_yanit" + "".join(f"_{v}" for v, _ in VARYANTLAR if len(sys.argv) > 1)


def main():
    import code_interpreter as CI
    import llm_client

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    llm = llm_client.load_model()

    yakalanan = {}
    gercek = CI.call_llm_text

    EMIN = ' Emin degilsen "TAMAM" yaz.'

    def sarmal(l, p):
        assert EMIN in p
        if yakalanan.get("_emin_yok"):
            p = p.replace(EMIN, "")
        p = p + (EK_EXPLAIN if yakalanan.get("_ek") else "")
        v = gercek(l, p)
        yakalanan["prompt"], yakalanan["yanit"] = p, v
        return v

    CI.call_llm_text = sarmal

    kayit = []
    for qid, v in VAKALAR.items():
        for varyant, tekrar in VARYANTLAR:
            yakalanan["_ek"] = varyant in ("VE", "VNE")
            yakalanan["_emin_yok"] = varyant in ("VN", "VNE")
            for n in range(tekrar):
                issue = CI._semantic_check(v["soru"], v["kod"], v["sonuc"], llm, verbose=False)
                k = {"id": qid, "varyant": varyant, "tekrar": n + 1,
                     "itiraz_mi": issue is not None, "ham_yanit": yakalanan["yanit"]}
                if varyant == "V0" and n == 0:
                    k["prompt"] = yakalanan["prompt"]
                kayit.append(k)
                print(f"#{qid} {varyant}[{n + 1}] itiraz={k['itiraz_mi']}: {k['ham_yanit']!r}", flush=True)

    with open(HERE / f"{ADI}.jsonl", "w", encoding="utf-8") as f:
        for k in kayit:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
