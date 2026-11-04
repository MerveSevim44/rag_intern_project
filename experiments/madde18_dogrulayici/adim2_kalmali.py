"""
Madde 18 Adım 2 — 7 "kalmalı" vakada (#32, #35, #39, #42, #52, #60, #108) tanı
varyantlarının BEDELİ: gerekçe-önce biçim doğru sonuçlara da itiraz ediyor mu?
(özellikle #57'deki "grafik yok" tarzı itirazlar). Adım 1 ile aynı düzenek
(adim1_ham_yanit.py: gerçek _semantic_check prompt'u, yalnız metin değişir).

  V0  bugünkü prompt            VE   gerekçe-önce (+ "Emin degilsen TAMAM")
  VNE "Emin degilsen" çıkarılmış + gerekçe-önce

Kod/sonuç: experiments/validator_A/results/log_gecis_1.txt (doğrulayıcının
production'da gördüğü deneme). #60: production'da 3. (son) denemede çözüldüğü için
doğrulayıcı HİÇ çağrılmıyor (attempt < max_retries); burada yalnız "çağrılsaydı"
davranışı için dahil.
Tanı amaçlı ayrıştırma (ürün DEĞİL): yanıtta SORUN / TAMAM geçiyor mu, SON hüküm ne.

Kullanım (kökten): python -u experiments/madde18_dogrulayici/adim2_kalmali.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT)]

VAKALAR = {
    "32": dict(
        soru="statistics bölümüne göre veri setinde toplam kaç profil (profileCount), kaç sektör (sectorCount) ve kaç meslek (occupationCount) bulunmaktadır?",
        kod="""result = {
    'profileCount': df['profileType'].count(),
    'sectorCount': df['sector'].nunique(),
    'occupationCount': df['occupation'].nunique()
}""",
        sonuc="{'profileCount': np.int64(728), 'sectorCount': 22, 'occupationCount': 91}"),
    "35": dict(
        soru="publicContact alanı altında phoneVisible ve emailVisible değerleri örnek profillerde genellikle nasıl ayarlanmıştır?",
        kod="result = df[['publicContact.phoneVisible', 'publicContact.emailVisible']].value_counts().to_dict()",
        sonuc="{(False, False): 728}"),
    "39": dict(
        soru="Umut Aslan profilinde services dizisindeki hizmetlerden hangileri Online, hangileri Yüz yüze modda sunulmaktadır?",
        kod="""# Umut Aslan profilini filtrele
mutum_aslan_profile = df[df['displayName'] == 'Umut Aslan']

# services sütununu JSON formatından listeye dönüştür
services_list = mutum_aslan_profile['services'].iloc[0]

# Online ve Yüz yüze hizmetleri ayırt et
online_services = [service for service in services_list if service['appointmentMode'] == 'Online']
face_to_face_services = [service for service in services_list if service['appointmentMode'] == 'Yüz yüze']

# Sonuçları sözlük olarak döndür
result = {
    'Online Services': online_services,
    'Face to Face Services': face_to_face_services
}""",
        sonuc="{'Online Services': [{'name': 'Gelişim görüşmesi', 'durationMinutes': 60, 'description': 'Gelişim görüşmesi için önceden planlanan birebir randevu.', 'appointmentMode': 'Online'}, {'name': 'Yetkinlik değerlendirme', 'durationMinutes': 30, 'description': 'Yetkinlik değerlendirme için önceden planlanan birebir randevu.', 'appointmentMode': 'Online'}], 'Face to Face Services': [{'name': 'Kariyer görüşmesi', 'durationMinutes': 30, 'description': 'Kariyer görüşmesi için önceden planlanan birebir randevu.', 'appointmentMode': 'Yüz yüze'}]}"),
    "42": dict(
        soru="Emre Korkmaz ve Umut Aslan profillerinin minimumNoticeHours ve cancellationNoticeHours değerlerini bir çubuk grafikle karşılaştırdığınızda nasıl bir fark ortaya çıkar?",
        kod="""# Emre Korkmaz ve Umut Aslan profillerini filtreleyelim
emre_profile = df[df['displayName'] == 'Emre Korkmaz']
umut_profile = df[df['displayName'] == 'Umut Aslan']

# Minimum Notice Hours ve Cancellation Notice Hours değerlerini alalım
emre_values = {
    'Minimum Notice Hours': emre_profile['appointmentSettings.minimumNoticeHours'].values[0],
    'Cancellation Notice Hours': emre_profile['appointmentSettings.cancellationNoticeHours'].values[0]
}

umut_values = {
    'Minimum Notice Hours': umut_profile['appointmentSettings.minimumNoticeHours'].values[0],
    'Cancellation Notice Hours': umut_profile['appointmentSettings.cancellationNoticeHours'].values[0]
}

# Farkları hesaplayalım
result = {
    'Emre Korkmaz': emre_values,
    'Umut Aslan': umut_values,
    'Fark Minimum Notice Hours': emre_values['Minimum Notice Hours'] - umut_values['Minimum Notice Hours'],
    'Fark Cancellation Notice Hours': emre_values['Cancellation Notice Hours'] - umut_values['Cancellation Notice Hours']
}""",
        sonuc="{'Emre Korkmaz': {'Minimum Notice Hours': np.int64(6), 'Cancellation Notice Hours': np.int64(24)}, 'Umut Aslan': {'Minimum Notice Hours': np.int64(4), 'Cancellation Notice Hours': np.int64(24)}, 'Fark Minimum Notice Hours': np.int64(2), 'Fark Cancellation Notice Hours': np.int64(0)}"),
    "52": dict(
        soru="22 sektörden 3 tanesinin (Sağlık, Spor ve Fitness, Eğitim ve Özel Ders) 40 profille diğerlerinden fazla temsil edilmesini bir dağılım grafiğinde görselleştirdiğinizde, bu dengesizliğin veri setinin sektörel analizine olası etkisi nedir?",
        kod="""# Sektorleri ve ilgili profilleri ayırt et
health_sectors = ['Sağlık', 'Spor ve Fitness', 'Eğitim ve Özel Ders']
other_sectors = [sector for sector in df['sector'].unique() if sector not in health_sectors]

# Sektorlara göre profiller sayısını say
sector_counts = df[df['sector'].isin(health_sectors)]['sector'].value_counts()

# Diğer sektörlerden fazla olan 40 profil bul
top_40_health_profiles = sector_counts.nlargest(40)

# Diğer sektörlerden fazla olan diğer sektörlerin sayısını say
other_sectors_count = df[~df['sector'].isin(health_sectors)]['sector'].value_counts()

# Grafik için verileri hazırla
sectors = top_40_health_profiles.index.tolist()
counts = top_40_health_profiles.values.tolist()
other_sectors_count = other_sectors_count.to_dict()

# Grafik oluşturmak için gerekli verileri getir
other_sectors_other_count = sum(other_sectors_count.values()) - other_sectors_count.get('Sağlık', 0)
other_sectors_other_count = other_sectors_count.get('Spor ve Fitness', 0) + other_sectors_count.get('Eğitim ve Özel Ders', 0)

# Sonuçları bir sözlükte döndür
result = {
    'Sektorler': sectors,
    'Sayılar': counts,
    'Diğer Sektorlerden Fazla Sayı': other_sectors_other_count
}

# Dengesizliğin potansiyel etkileri
result['Etkiler'] = [
    "Sağlık sektöründeki yoğun representasyon, diğer sektörlerin profil sayısını azaltabilir.",
    "Bu dengesizlik, kullanıcıların diğer sektörlerdeki profesyonelleri aramakta zorlanmalarına neden olabilir.",
    "Sağlık sektörünün diğer sektörlerden daha fazla profil olması, kullanıcıların bu sektördeki profesyonelleri tercih etmelerine yol açabilir.",
    "Bu durum, diğer sektörlerin profesyonellerinin mevcut müşterilerini kaybetmelerine ve yeni müşteriler kazanmalarına engel olabilir."
]""",
        sonuc="{'Sektorler': ['Sağlık', 'Spor ve Fitness', 'Eğitim ve Özel Ders'], 'Sayılar': [40, 40, 40], 'Diğer Sektorlerden Fazla Sayı': 0, 'Etkiler': ['Sağlık sektöründeki yoğun representasyon, diğer sektörlerin profil sayısını azaltabilir.', 'Bu dengesizlik, kullanıcıların diğer sektörlerdeki profesyonelleri aramakta zorlanmalarına neden olabilir.', 'Sağlık sektörünün diğer sektörlerden daha fazla profil olması, kullanıcıların bu sektördeki profesyonelleri tercih etmelerine yol açabilir.', 'Bu durum, diğer sektörlerin profesyonellerinin mevcut müşterilerini kaybetmelerine ve yeni müşteriler kazanmalarına engel olabilir.']}"),
    "60": dict(
        soru="Profillerin deneyim yıllarını (experience.years) bir histogramla görselleştirdiğinizde veri setindeki deneyim dağılımı nasıl bir eğilim göstermektedir?",
        kod="""# Deneyim yıllarındaki dağılımı görselleştirmek için histogram oluşturuyoruz
result = df['experience.years'].value_counts().sort_index().to_frame().reset_index()
result.columns = ['Deneyim_Yılları', 'Profil_Sayısı']
result = result.to_dict('records')

# Sonuçları 'result' değişkenine atıyoruz
result""",
        sonuc="[{'Deneyim_Yılları': 2, 'Profil_Sayısı': 36}, {'Deneyim_Yılları': 3, 'Profil_Sayısı': 28}, {'Deneyim_Yılları': 4, 'Profil_Sayısı': 40}, {'Deneyim_Yılları': 5, 'Profil_Sayısı': 31}, {'Deneyim_Yılları': 6, 'Profil_Sayısı': 37}, {'Deneyim_Yılları': 7, 'Profil_Sayısı': 39}, {'Deneyim_Yılları': 8, 'Profil_Sayısı': 35}, {'Deneyim_Yılları': 9, 'Profil_Sayısı': 32}, {'Deneyim_Yılları': 10, 'Profil_Sayısı': 40}, {'Deneyim_Yılları': 11, 'Profil_Sayısı': 26}, {'Deneyim_Yılları': 12, 'Profil_Sayısı': 35}, {'Deneyim_Yılları': 13, 'Profil_Sayısı': 40}, {'Deneyim_Yılları': 14, 'Profil_Sayısı': 31}, {'Deneyim_Yılları': 15, 'Profil_Sayısı': 39}, {'Deneyim_Yılları': 16, 'Profil_Sayısı': 26}, {'Deneyim_Yılları': 17, 'Profil_Sayısı': 36}, {'Deneyim_Yılları': 18, 'Profil_Sayısı': 39}, {'Deneyim_Yılları': 19, 'Profil_Sayısı': 42}, {'Deneyim_Yılları': 20, 'Profil_Sayısı': 27}, {'Deneyim_Yılları': 21, 'Profil_Sayısı': 30}, {'Deneyim_Yılları': 22, 'Profil_Sayısı': 39}]"),
    "108": dict(
        soru="728_profiles.json veri setinde profillerin cinsiyet dağılımı nedir?",
        kod="""result = {
    'Individual': df[df['profileType'] == 'individual'].shape[0],
    'Business': df[df['profileType'] == 'business'].shape[0]
}""",
        sonuc="{'Individual': 599, 'Business': 129}"),
}

EMIN = ' Emin degilsen "TAMAM" yaz.'
EK_EXPLAIN = ("\n\n[TANI] Cevap vermeden once 1-2 cumleyle gerekcesini yaz "
              "(soru ne istiyor, kod ne yapiyor, uyusuyor mu), sonra son satira "
              "TAMAM veya SORUN: <tek cumle> yaz.")


def hukum(yanit):
    """Tanı amaçlı: yanıtta SORUN/TAMAM geçişleri ve SON hüküm."""
    gecisler = re.findall(r"SORUN|TAMAM", yanit)
    return {"sorun_var": "SORUN" in gecisler, "tamam_var": "TAMAM" in gecisler,
            "son": gecisler[-1] if gecisler else None}


def main():
    import code_interpreter as CI
    import llm_client

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    llm = llm_client.load_model()
    durum = {}
    gercek = CI.call_llm_text

    def sarmal(l, p):
        assert EMIN in p
        if durum["varyant"] == "VNE":
            p = p.replace(EMIN, "")
        if durum["varyant"] in ("VE", "VNE"):
            p += EK_EXPLAIN
        durum["yanit"] = gercek(l, p)
        return durum["yanit"]

    CI.call_llm_text = sarmal
    kayit = []
    for qid, v in VAKALAR.items():
        for varyant in ("V0", "VE", "VNE"):
            durum["varyant"] = varyant
            CI._semantic_check(v["soru"], v["kod"], v["sonuc"], llm, verbose=False)
            h = hukum(durum["yanit"])
            kayit.append({"id": qid, "varyant": varyant, **h, "ham_yanit": durum["yanit"]})
            print(f"#{qid} {varyant}: son={h['son']} sorun_var={h['sorun_var']} | {durum['yanit'][:600]!r}", flush=True)
    with open(HERE / "adim2_kalmali.jsonl", "w", encoding="utf-8") as f:
        for k in kayit:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
