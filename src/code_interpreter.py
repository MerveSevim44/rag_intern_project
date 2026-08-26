"""
code_interpreter.py — Dinamik Text-to-Pandas & Hata Düzeltme Döngüsü (Self-Correction)

Bu modül:
1. DataFrame'in anlık şemasını (dtypes, örnek kayıtlar) kullanarak LLM'e kod üretim promptu hazırlar.
2. Üretilen kodu sandbox içinde çalıştırır.
3. Hata alınırsa (Syntax, KeyError, Timeout vb.) hata mesajını LLM'e geri besleyerek (retry loop) düzeltmesini ister.
4. Hesaplanan pandas sonucunu doğal dilde (Türkçe) özetler.
5. Başarısızlık durumunda Semantik RAG'e devretmek üzere güvenli fallback sağlar.
"""

import sys
import json
import re
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np

try:
    from src.sandbox import safe_execute, clean_python_code
except ImportError:
    from sandbox import safe_execute, clean_python_code


# "net bakiye", "net değişim", "toplam credit - toplam debit" gibi işaretli
# toplam gerektiren ifadeler. Bu kalıplar YOKSA few-shot prompt'a eklenmez.
SIGNED_SUM_TRIGGERS = [
    r"net\s+bakiye",
    r"net\s+de[gğ]i[sş]im",
    r"net\s+(toplam|tutar|ak[ıi][sş])",
    r"bakiye\s+de[gğ]i[sş]im",
    r"credit\s*[-–]\s*debit",
    r"alacak\s*[-–]\s*bor[cç]",
    r"(toplam\s+credit).{0,20}(toplam\s+debit)",
]

# credit/debit ikilisini taşıyan işaret kolonunu tanımak için
_SIGN_VALUE_SETS = [
    ({"credit", "debit"}, "credit"),
    ({"alacak", "borç"}, "alacak"),
    ({"in", "out"}, "in"),
    ({"giriş", "çıkış"}, "giriş"),
]


def _find_sign_column(df: pd.DataFrame):
    """
    df'te credit/debit (veya eşdeğeri) ikilisini taşıyan kolonu ve pozitif değerini bulur.
    Bulamazsa (None, None) döner — bu durumda signed-sum few-shot eklenmez.
    """
    for col in df.columns:
        try:
            series = df[col]
            if series.dtype != object:
                continue
            uniques = {str(u).strip().lower() for u in series.dropna().unique()}
            if not uniques or len(uniques) > 6:
                continue
            for value_set, positive in _SIGN_VALUE_SETS:
                if value_set.issubset(uniques):
                    return str(col), positive
        except Exception:
            continue
    return None, None


def _find_amount_column(df: pd.DataFrame):
    """Signed-sum örneğinde kullanılacak sayısal tutar kolonunu seçer."""
    preferred = ["amount", "tutar", "value", "miktar", "total", "price"]
    numeric = [str(c) for c in df.columns
               if pd.api.types.is_numeric_dtype(df[c])]
    for name in preferred:
        for col in numeric:
            if col.lower() == name:
                return col
    return numeric[0] if numeric else None


def _build_signed_sum_fewshot(question: str, df: pd.DataFrame) -> str:
    """
    (A) Yalnızca soru "net bakiye / net değişim / credit - debit" kalıplarından
    birini içeriyorsa VE df'te credit/debit işaret kolonu varsa hedefli bir
    few-shot örneği döner. Aksi hâlde boş string döner; böylece groupby/filtre
    soruları (Q3, Q5) bu kuraldan hiç etkilenmez.
    """
    q = question.strip().lower()
    if not any(re.search(pat, q, re.IGNORECASE) for pat in SIGNED_SUM_TRIGGERS):
        return ""

    sign_col, positive = _find_sign_column(df)
    amount_col = _find_amount_column(df)
    if not sign_col or not amount_col:
        return ""

    values = [str(u) for u in df[sign_col].dropna().unique()]
    negative = next((v for v in values if v.strip().lower() != positive), "debit")
    positive_actual = next((v for v in values if v.strip().lower() == positive), positive)

    # Senaryo karşılaştırması: "pending dahil edilirse ne kadar farklılaşır?" gibi
    # sorularda tek bir senaryoyu hesaplamak cevabı tamamen yanlış yapar.
    delta_triggers = [r"dahil edilir", r"dahil edildi", r"hari[cç] tutul", r"farkl[ıi]la[sş]",
                      r"ne kadar de[gğ]i[sş]", r"kar[sş][ıi]la[sş]t[ıi]r"]
    delta_block = ""
    if any(re.search(pat, q, re.IGNORECASE) for pat in delta_triggers):
        delta_block = f"""

DİKKAT — BU SORU İKİ SENARYONUN FARKINI İSTİYOR:
Tek bir filtre uygulayıp tek sonuç döndürmek YANLIŞTIR. İki net değeri AYRI AYRI hesapla
(ör. dar kapsam = yalnızca bir durum, geniş kapsam = ek durum(lar) dahil), sonra farkı al:
result = {{'dar_kapsam_net': ..., 'genis_kapsam_net': ..., 'fark': genis - dar}}"""

    return f"""

ZORUNLU HESAPLAMA BİÇİMİ (bu soru İŞARETLİ TOPLAM gerektiriyor):{delta_block}
'{sign_col}' kolonu yön/işaret bilgisi taşır: '{positive_actual}' artı (+),
'{negative}' eksi (-) yöndedir. '{amount_col}' kolonundaki değerler HER ZAMAN
pozitif saklanır; bu yüzden hepsini düz toplamak MATEMATİKSEL OLARAK YANLIŞTIR.
Aşağıdaki iki formdan BİRİNİ aynen kullan:

# Form 1 — np.where ile işaretli toplam
net = np.where(df['{sign_col}'] == '{positive_actual}', df['{amount_col}'], -df['{amount_col}']).sum()

# Form 2 — groupby ile credit/debit farkı
gruplar = df.groupby('{sign_col}')['{amount_col}'].sum()
net = gruplar.get('{positive_actual}', 0) - gruplar.get('{negative}', 0)

Soruda belirtilen filtreleri (hesap no, durum, tarih aralığı) bu hesaptan ÖNCE df'e uygula.
result'a hem bileşenleri hem de net değeri koy:
result = {{'{positive_actual}_toplam': ..., '{negative}_toplam': ..., 'net': ...}}"""


def _build_currency_rule(df: pd.DataFrame) -> str:
    """
    (B) Para birimi kolonu varsa, birimin VERİDEN okunmasını zorunlu kılan kural.
    Model aksi hâlde Türkçe cevapta varsayılan olarak 'TL' uyduruyordu.
    """
    currency_cols = [str(c) for c in df.columns
                     if str(c).lower() in ("currency", "para_birimi", "currency_code", "birim")]
    if not currency_cols:
        return ""
    col = currency_cols[0]
    try:
        uniques = [str(u) for u in df[col].dropna().unique()][:5]
    except Exception:
        uniques = []
    return (
        f"\n9. Sonuç parasal bir tutar ise para birimini ASLA varsayma ve ASLA 'TL' yazma. "
        f"Birimi mutlaka veriden oku: df['{col}'].unique() (filtre uyguladıysan filtrelenmiş "
        f"alt kümenin '{col}' değerini kullan) ve result sözlüğüne 'currency' anahtarıyla ekle. "
        f"Bu veri setindeki mevcut değerler: {uniques}."
    )



# ─────────────────────────────────────────────────────────────────────────────
# GENEL ANALİTİK YETENEK KATMANI (dataset-agnostik)
#
# Buradaki hiçbir kural belirli bir dosyaya/kolon adına bağlı DEĞİLDİR. İki
# kaynaktan beslenir:
#   (1) SORUNUN matematiksel niyeti (mesafe, oran, fark, uç değer, eşik...),
#   (2) df'in KOLON İMZALARI (ör. "sayısal ve coğrafi koordinat aralığında bir
#       enlem/boylam çifti var mı?") — kolonun adı değil, taşıdığı anlam.
# Böylece airports.json'a özel bir şey eklemeden, koordinat taşıyan HERHANGİ
# bir JSON veri setinde aynı yetenek çalışır.
# ─────────────────────────────────────────────────────────────────────────────

UNIVERSAL_CODE_RULES = """
ÇOK ADIMLI HESAPLAMA DİSİPLİNİ (her soru için geçerli):
- Ara adımlar için SERBESTÇE ara değişken kullan. Yardımcı fonksiyon (def) ve
  lambda tanımlayabilirsin; bunların içinden df, pd, np, math ve daha önce
  tanımladığın değişkenler görünür.
- 'result' SADECE ve SADECE en son satırda, bir kez atanır. 'result'ı ara değer
  tutmak için ASLA kullanma (önce result'a bir satır atayıp sonra üstüne yazmak
  tipik ve yıkıcı bir hatadır).
- Kullanilabilir araclar: pandas (pd), numpy (np), math ve ortamda HAZIR TANIMLI
  yardimci fonksiyonlar: haversine(lat1, lon1, lat2, lon2) -> km,
  percent_change(old, new) -> %. Bu hazir fonksiyonlari YENIDEN TANIMLAMA, dogrudan
  cagir. BASKA kutuphane YOK (geopy, sklearn, scipy, datetime modulu vb. yoktur).
- Kendi tanimladigin bir yardimci fonksiyonu cagirmadan ONCE mutlaka def ile tanimla;
  tanimsiz bir fonksiyonu cagirmak NameError verir.
- Soru bir EŞİK/KOŞUL içeriyorsa ("birden fazla", "en az N", "yalnızca ...",
  "... olanlar") sonucu MUTLAKA bu koşulla FİLTRELE; koşulu sağlamayan satırları
  sonuçta bırakma.
- Soru birden fazla bilgi istiyorsa (isim + değer, iki uç + fark) hepsini TEK bir
  sözlükte döndür ve anahtarları açıklayıcı yaz.
- Uç değer seçerken kavramın YÖNÜNÜ doğrula: "en büyük/en yüksek/en kuzey/en yeni"
  -> idxmax; "en küçük/en düşük/en güney/en eski" -> idxmin. Etiketi ve sayısal
  değeri AYNI satırdan al (df.loc[idx]) ki eşleşme kaymasın.
- Bir varlığı ararken kod/kısaltma kolonunu tercih et; eşleşme boş çıkarsa .iloc[0]
  IndexError verir — önce eşleşmenin boş olmadığından emin ol.
"""


def _numeric_columns(df: pd.DataFrame):
    return [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _column_tokens(name: str):
    """
    Kolon adini token'lara ayirir: snake_case, kebab, nokta ve camelCase sinirlari.
    'appointmentSettings.cancellationNoticeHours' -> {'appointment','settings',
    'cancellation','notice','hours'}. Alt dizge (substring) eslesmesi yerine token
    eslesmesi kullaniyoruz; aksi halde 'cancellation' icindeki 'lat' yuzunden
    tamamen alakasiz bir kolon 'enlem' sanilabiliyor.
    """
    parts = re.split(r"[^A-Za-z0-9]+", str(name))
    tokens = set()
    for part in parts:
        for tok in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|[0-9]+", part):
            tokens.add(tok.lower())
    return tokens


_LAT_TOKENS = {"lat", "lats", "latitude", "enlem"}
_LON_TOKENS = {"lon", "lng", "long", "longitude", "boylam"}


def _detect_coordinate_pair(df: pd.DataFrame):
    """
    df'te bir (enlem, boylam) cifti var mi? Iki kosul birlikte aranir:
      1. Ad token'i: kolon adinda 'lat'/'enlem' ve 'lon'/'lng'/'boylam' token'i,
      2. Deger araligi: enlem [-90, 90], boylam [-180, 180] ve sayisal.
    Ikisi de zorunludur — yalnizca aralik bakmak 'autoApproveRequests' gibi 0/1
    kolonlarini, yalnizca ada bakmak da alakasiz metrikleri koordinat sanmaya
    yol acar. Kolon ADI hicbir veri setine ozel degildir; sadece "enlem/boylam"
    kavraminin yaygin yazimlaridir.

    Doner: (lat_col, lon_col) veya (None, None).
    """
    lat_col = lon_col = None
    for col in _numeric_columns(df):
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 2:
            continue
        lo, hi = float(series.min()), float(series.max())
        tokens = _column_tokens(col)
        if lat_col is None and (tokens & _LAT_TOKENS) and -90.0 <= lo and hi <= 90.0:
            lat_col = str(col)
        elif lon_col is None and (tokens & _LON_TOKENS) and -180.0 <= lo and hi <= 180.0:
            lon_col = str(col)

    if lat_col and lon_col and lat_col != lon_col:
        return lat_col, lon_col
    return None, None


_DISTANCE_INTENT = [
    r"mesafe", r"uzakl[iı]k", r"en\s+yak[iı]n", r"en\s+uzak", r"km",
    r"kilometre", r"haversine", r"b[uü]y[uü]k\s+daire", r"great\s*circle",
    r"distance", r"nearest", r"closest", r"yar[iı][cç]ap",
]


def _build_geo_recipe(question: str, df: pd.DataFrame) -> str:
    """
    Soruda mesafe niyeti VARSA ve df'te koordinat çifti bulunuyorsa haversine
    reçetesini enjekte eder; aksi hâlde boş string döner.

    Neden: küçük modeller mesafeyi ya Öklid ile ((dlat**2+dlon**2)**0.5) yaklaşık
    hesaplıyor (derece != km, üstelik boylamın km karşılığı enleme göre değişir),
    ya da sandbox'ta olmayan geopy'yi çağırıyor. Reçete veri setine değil,
    "koordinat + mesafe" KAVRAMINA bağlıdır.
    """
    q = question.strip().lower()
    if not any(re.search(pat, q, re.IGNORECASE) for pat in _DISTANCE_INTENT):
        return ""
    lat_col, lon_col = _detect_coordinate_pair(df)
    if not lat_col or not lon_col:
        return ""

    return f"""

ZORUNLU FORMUL - COGRAFI MESAFE:
Bu soru koordinatlar arasi mesafe istiyor. '{lat_col}' enlem, '{lon_col}' boylamdir.
Oklid mesafesi ((dlat**2 + dlon**2)**0.5) KESINLIKLE YANLISTIR (derece != km) ve
geopy gibi bir kutuphane YOKTUR.

Ortamda HAZIR TANIMLI bir fonksiyon var, onu DOGRUDAN cagir; ASLA yeniden tanimlama
ve asla kendi mesafe formulunu yazma:

    haversine(lat1, lon1, lat2, lon2) -> km cinsinden buyuk daire mesafesi

Skaler de Series de kabul eder (vektorel calisir). Iki nokta arasi:
    a = df[df['<kod_kolonu>'] == '<deger1>'].iloc[0]
    b = df[df['<kod_kolonu>'] == '<deger2>'].iloc[0]
    result = round(haversine(a['{lat_col}'], a['{lon_col}'], b['{lat_col}'], b['{lon_col}']), 2)

Bir referans satira olan TUM mesafeler icin referansin KENDISINI disla
(kendine uzaklik 0'dir, "en yakin" listesini bozar):
    ref = df[df['<kod_kolonu>'] == '<deger>'].iloc[0]
    others = df[df.index != ref.name].copy()
    others['distance_km'] = haversine(ref['{lat_col}'], ref['{lon_col}'],
                                      others['{lat_col}'], others['{lon_col}']).round(2)
    result = others.nsmallest(3, 'distance_km')[['<ad_kolonu>', 'distance_km']].to_dict('records')"""


def build_code_gen_prompt(question: str, df: pd.DataFrame) -> str:
    """
    DataFrame'in gerçek şemasına ve örnek satırlarına dayalı, kolon uydurmayı
    engelleyen kod üretim promptunu oluşturur.
    """
    # Kolonlar ve tipleri
    dtypes_dict = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
    
    # İlk 2 satır örnek kayıtlar (özet için)
    try:
        sample_records = df.head(2).to_dict(orient="records")
        # Örnek veriyi JSON olarak serileştirilebilir hale getir
        sample_json = json.dumps(sample_records, ensure_ascii=False, default=str)
    except Exception:
        sample_json = str(df.head(2).to_dict())

    # Düşük kardinaliteli (kategorik) kolonların GERÇEK değerleri.
    # Bunlar olmadan model 'type' kolonunun credit/debit ayrımı taşıdığını bilemez
    # ve "net bakiye = credit - debit" gibi soruları tüm satırları toplayarak
    # yanlış hesaplar.
    categorical_lines = []
    for col in df.columns:
        try:
            series = df[col]
            if series.dtype != object:
                continue
            uniques = [u for u in series.dropna().unique() if isinstance(u, str)]
            if 0 < len(uniques) <= 15:
                categorical_lines.append(f"  - {col}: {uniques}")
        except Exception:
            continue
    categorical_info = (
        "\n- Kategorik Sütunların TÜM Olası Değerleri:\n" + "\n".join(categorical_lines)
        if categorical_lines else ""
    )

    # ── (A) Hedefli Signed-Sum Few-Shot ────────────────────────────────────
    # SADECE "net bakiye / net değişim / credit - debit" tipi sorularda ve SADECE
    # df'te credit/debit taşıyan bir işaret kolonu varsa devreye girer. Koşulsuz
    # eklendiğinde groupby/filtre sorularını (Q3, Q5) bozduğu için kapsam dar tutuldu.
    signed_shot = _build_signed_sum_fewshot(question, df)

    # ── (B) Para Birimi Kolonu ─────────────────────────────────────────────
    currency_rule = _build_currency_rule(df)

    # ── (C) Kavram tabanlı formül reçeteleri (dataset-agnostik) ────────────
    geo_recipe = _build_geo_recipe(question, df)

    schema_info = f"""Mevcut DataFrame (df) Bilgisi:
- Toplam Satır Sayısı: {len(df)}
- Tüm Sütun İsimleri (Birebir kullan): {list(df.columns)}
- Sütunlar ve Veri Tipleri: {dtypes_dict}
- İlk 2 Satır Örnek Kayıt: {sample_json}{categorical_info}"""

    return f"""Sen uzman bir Python ve Pandas veri analistisin. Aşağıdaki DataFrame (df) şemasına göre kullanıcının sorusunu cevaplayan Python/pandas kodu üret.

{schema_info}

Kurallar:
1. SADECE pandas/numpy ve Python standart veri yapılarını kullan.
2. Hesaplama veya filtreleme sonucunu MUTLAKA 'result' isimli değişkene ata (Örnek: result = ...).
3. Asla 'import' ifadesi yazma (pd ve np zaten tanımlıdır).
4. Dosya okuma (pd.read_csv, open vb.) yapma; veri 'df' değişkeninde zaten yüklüdür.
5. Açıklama, selamlama veya markdown yorumu yazma; SADECE çalıştırılabilir Python kodu üret.
6. Sütun isimlerini şemada verildiği gibi tam ve birebir kullan.
7. Eğer soru karşılaştırma, sıralama veya liste gerektiriyorsa sonucu açıklayıcı bir sözlük (dict), liste veya Series olarak 'result'a ata.
8. Soruda "net", "fark" veya "değişim" geçiyorsa ilgili grupları AYRI AYRI hesaplayıp çıkarma işlemini açıkça yaz; hepsini tek bir toplamda birleştirme.{currency_rule}
{UNIVERSAL_CODE_RULES}{geo_recipe}{signed_shot}

Soru: {question}

Kod:"""


def build_correction_prompt(question: str, df: pd.DataFrame,
                            history, repeated: bool = False) -> str:
    """
    Hata durumunda duzeltme promptu uretir.

    Eski surumde hata mesaji ve hatali kod EN BASA, devasa sema promptu ise SONA
    konuyordu. Kucuk modellerde recency baskin oldugu icin model prompt'un
    sonundaki "Soru: ... Kod:" kismina odaklanip AYNI hatali kodu 3 kez uretiyor,
    retry dongusu hicbir bilgi kazanci saglamadan tukeniyordu. Artik:
      - Tum basarisiz denemelerin gecmisi verilir (yalnizca sonuncusu degil),
      - Duzeltme talimati prompt'un EN SONUNA konur,
      - Ayni kod tekrar uretilirse acik bir "farkli yaklasim kullan" yasagi eklenir.
    """
    base_prompt = build_code_gen_prompt(question, df)

    attempts_block = "\n".join(
        f"--- Deneme {i} ---\nKod:\n{code}\nHATA: {err}\n"
        for i, (code, err) in enumerate(history, 1)
    )

    repeat_warning = ""
    if repeated:
        repeat_warning = (
            "\nCOK ONEMLI: Bir onceki denemeyle NEREDEYSE AYNI kodu urettin ve ayni "
            "hatayi aldin. Ayni kodu tekrar yazmak YASAK. Tamamen FARKLI bir yaklasim "
            "sec: zincirlenmis tek satirlik ifade yerine adim adim ara degiskenler "
            "kullan, pivot/agg gibi karmasik yapilar yerine basit filtreleme + "
            "aritmetik yaz.\n"
        )

    return f"""{base_prompt}

=== ONCEKI BASARISIZ DENEMELER (tekrarlama!) ===
{attempts_block}
=== DUZELTME GOREVI ===
Yukaridaki hatalarin KOK NEDENINI dusun ve bu kez CALISAN kodu yaz.{repeat_warning}
- NameError aliyorsan o ismi kodun icinde ONCE tanimla.
- KeyError aliyorsan kolon adini semadaki listeden birebir kopyala.
- Karmasik zincir (pivot/agg/unstack) hata veriyorsa onu birak, en basit yolu sec.
Sadece calistirilabilir Python kodu yaz, aciklama yazma. Sonucu 'result' degiskenine ata.

Soru: {question}

Kod:"""


def _normalize_code(code: str) -> str:
    """Tekrar tespiti icin kodu bosluk/yorumdan arindirilmis bicime indirger."""
    lines = []
    for line in (code or "").splitlines():
        line = re.sub(r"#.*$", "", line).strip()
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines))


def _bump_temperature(llm: Any, temperature: float):
    """
    Tekrar eden ciktiyi kirmak icin sicakligi yukseltilmis bir LLM klonu doner.
    Desteklenmiyorsa orijinal nesneyi doner (akis bozulmaz).
    """
    try:
        if hasattr(llm, "bind"):
            return llm.bind(temperature=temperature)
    except Exception:
        pass
    return llm


def call_llm_text(llm: Any, prompt_text: str) -> str:
    """LLM'i metin promptu ile çağırır ve metin yanıtını döner."""
    if hasattr(llm, "invoke"):
        response = llm.invoke(prompt_text)
        if hasattr(response, "content"):
            return str(response.content).strip()
        return str(response).strip()
    elif callable(llm):
        return str(llm(prompt_text)).strip()
    else:
        raise ValueError(f"Geçersiz LLM nesnesi: {type(llm)}")


def code_interpreter_with_retry(
    question: str,
    df: pd.DataFrame,
    llm: Any,
    max_retries: int = 3,
    timeout_seconds: int = 5,
    verbose: bool = True,
    self_check: bool = True
) -> Dict[str, Any]:
    """
    Kullanıcı sorusu için Pandas kodu üretir, sandbox'ta çalıştırır ve hata durumunda
    max_retries kadar self-correction (düzeltme) döngüsü uygular.

    Returns:
        {
            "success": True/False,
            "raw_result": hesaplanan nesne (veya None),
            "code": son çalıştırılan kod,
            "attempts": kaç deneme yapıldığı,
            "error": hata mesajı (varsa)
        }
    """
    fallback_result = None   # dogrulama uyarisi almis ama calisan ilk sonuc
    prompt = build_code_gen_prompt(question, df)
    history = []          # [(kod, hata)] - tum basarisiz denemeler
    seen_codes = set()    # tekrar uretilen kodu yakalamak icin
    last_code = ""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        if verbose:
            print(f"[CodeInterpreter] Deneme {attempt}/{max_retries}...")

        # Tekrar eden ciktiyi kirmak icin denemeyle birlikte sicakligi artir.
        active_llm = llm if attempt == 1 else _bump_temperature(llm, min(0.2 * attempt, 0.7))

        raw_code = call_llm_text(active_llm, prompt)
        code = clean_python_code(raw_code)
        last_code = code

        if verbose:
            print(f"[CodeInterpreter] Uretilen Kod:\n{code}")

        norm = _normalize_code(code)
        repeated = norm in seen_codes
        seen_codes.add(norm)

        exec_result = safe_execute(code, df, timeout_seconds=timeout_seconds)

        if isinstance(exec_result, dict) and "error" in exec_result:
            last_error = exec_result["error"]
            if verbose:
                print(f"[CodeInterpreter] Hata alindi ({attempt}. deneme): {last_error}")
            history.append((code, last_error))
            prompt = build_correction_prompt(question, df, history, repeated=repeated)
            continue

        # --- Basarili calistirma: semantik dogrulama katmani ----------------
        # Kod HATASIZ calissa bile soruyu yanlis yorumlamis olabilir (uc deger
        # etiketlerinin ters atanmasi, istenen filtrenin uygulanmamasi gibi).
        # Bu kontrol veri setinden bagimsizdir: yalnizca soru + kod + sonuc
        # uclusunun tutarliligina bakar.
        if self_check and attempt < max_retries:
            issue = _semantic_check(question, code, exec_result, llm, verbose=verbose)
            if issue:
                history.append((code, f"Kod calisti ama sonuc soruyla tutarsiz: {issue}"))
                prompt = build_correction_prompt(question, df, history, repeated=repeated)
                # Ilk calisan sonucu yedekte tut ki duzeltme denemesi de tutmazsa
                # elimizde hicbir sey kalmasin.
                if fallback_result is None:
                    fallback_result = {"success": True, "raw_result": exec_result,
                                       "code": code, "attempts": attempt, "error": None,
                                       "warning": issue}
                continue

        if verbose:
            print(f"[CodeInterpreter] Basarili! Cikti: {exec_result}")
        return {
            "success": True,
            "raw_result": exec_result,
            "code": code,
            "attempts": attempt,
            "error": None
        }

    # Dogrulama uyarili ama calisan bir sonuc varsa onu dondur (fallback'e dusme).
    if fallback_result is not None:
        if verbose:
            print("[CodeInterpreter] Dogrulama uyarili sonuc donduruluyor.")
        return fallback_result

    if verbose:
        print(f"[CodeInterpreter] {max_retries} deneme basarisiz oldu. Son hata: {last_error}")
    return {
        "success": False,
        "raw_result": None,
        "code": last_code,
        "attempts": max_retries,
        "error": f"{max_retries} denemede cozulemedi: {last_error}"
    }


def _semantic_check(question: str, code: str, result: Any, llm: Any,
                    verbose: bool = True) -> Optional[str]:
    """
    Hatasiz calisan kodun soruyu DOGRU yorumlayip yorumlamadigini denetler.
    Sorun yoksa None, varsa kisa bir aciklama doner.

    Muhafazakar tasarim: model kararsizsa None doner (dogru sonucu bosa
    harcamamak icin); yalnizca cevap 'SORUN:' ile basliyorsa itiraz sayilir.
    """
    preview = str(result)
    if len(preview) > 1200:
        preview = preview[:1200] + " ..."

    prompt = f"""Bir veri analisti asagidaki soruyu pandas kodu ile cevapladi. Kod hatasiz calisti.
Gorevin SADECE mantik denetimi yapmak.

Soru: {question}

Kod:
{code}

Uretilen sonuc: {preview}

Sunlari kontrol et:
1. Soruda istenen filtre/esik (or. "birden fazla", "en az N", "yalnizca X") koda uygulanmis mi?
2. Uc deger etiketleri dogru yonde mi (en buyuk -> idxmax, en kucuk -> idxmin)?
3. Sonuc, sorunun istedigi TUM bilgileri iceriyor mu?
4. Kullanilan formul soruda istenen formul mu?

Kod soruyu dogru cevapliyorsa SADECE "TAMAM" yaz.
Somut ve kesin bir hata varsa "SORUN: <tek cumle>" yaz. Emin degilsen "TAMAM" yaz.

Cevap:"""
    try:
        verdict = call_llm_text(llm, prompt).strip()
    except Exception:
        return None

    if verdict.upper().startswith("SORUN"):
        issue = verdict.split(":", 1)[-1].strip()[:300]
        if verbose:
            print(f"[CodeInterpreter] Semantik dogrulama itirazi: {issue}")
        return issue or None
    return None


def result_to_natural_language(question: str, result: Any, llm: Any) -> str:
    """
    Hesaplanan ham Pandas sonucunu (Sayı, Liste, Sözlük, Seri, DataFrame)
    akıcı, net ve sayıları değiştirmeyen Türkçe bir cümleye dönüştürür.
    """
    # Sonucu okunabilir formata sok
    if isinstance(result, pd.DataFrame):
        formatted_result = result.to_dict(orient="records")
    elif isinstance(result, pd.Series):
        formatted_result = result.to_dict()
    elif isinstance(result, np.generic):
        formatted_result = result.item()
    else:
        formatted_result = result

    prompt = f"""Kullanıcı Sorusı: {question}
Hesaplanan Veri / Matematiksel Sonuç: {formatted_result}

Görev: Yukarıdaki hesaplama sonucunu kullanıcıya yönelik kısa, net, doğrudan ve doğal bir Türkçe cümle ile özetle.
ONEMLI KURAL: Sayilari, oranlari, siralamalari ve isimleri asla degistirme veya uydurma,
tam olarak hesaplama sonucunda ne varsa onu aktar.
EK SAYI YASAGI: Hesaplama sonucunda GECMEYEN hicbir sayiyi cumleye ekleme. Donusum,
tahmin, yaklasik esdeger ("yaklasik X'e esittir") veya ek yorum YAZMA. Sadece sonuctaki
degerleri aktar ve orada bitir.
PARA BİRİMİ KURALI: Sonuca kendiliğinden para birimi EKLEME. 'TL', 'lira', '₺', '$', 'dolar'
gibi bir birim UYDURMA. Yalnızca yukarıdaki hesaplama sonucunda bir para birimi (ör.
currency: USD) AÇIKÇA yer alıyorsa o birimi HARFİ HARFİNE kullan — kodu sembole çevirme,
'USD' gördüysen 'USD' yaz, asla '$' veya 'dolar' yazma. Sonuçta birim yoksa sayıyı birimsiz yaz.

Cevap:"""

    try:
        natural_text = call_llm_text(llm, prompt).strip()
    except Exception:
        return f"Hesaplama Sonucu: {formatted_result}"

    # Prompt kurali tek basina yetmiyor: model hesaplama sonucunda hic para birimi
    # olmasa bile cumlenin sonuna 'TL' ekleyebiliyor. Deterministik son katman.
    try:
        try:
            from src.llm_client import _fix_currency_hallucination
        except ImportError:
            from llm_client import _fix_currency_hallucination
        natural_text = _fix_currency_hallucination(natural_text, str(formatted_result))
    except Exception:
        pass

    # Para birimi temizliginden geriye kalabilen bos parantez/artik noktalama.
    natural_text = re.sub(r"\(\s*\)", "", natural_text)
    natural_text = re.sub(r"\s{2,}", " ", natural_text).strip()

    return natural_text
