# Dinamik Text-to-Pandas Sandbox & Çoklu JSON Doğrulama Raporu

Kullanıcı talebi doğrultusunda **Dinamik Text-to-Pandas Sandbox**, **3 Kademeli Akıllı Yönlendirici (Router)**, **Hata Düzeltme (Retry) Döngüsü** ve **Doğal Dil Sentezleyici** mimarisi geliştirilmiş ve hem `728_profiles.json` hem de `data/airports.json` veri setlerinde başarıyla test edilmiştir.

---

## 1. Mimari Bileşenleri ve Yapılan Geliştirmeler

### 1. 3 Kademeli Akıllı Router ([`router.py`](file:///c:/Users/merve/Desktop/rag_project/router.py))
- **`rule_engine` (1. Aşama)**: Önceden tanımlı veya basit tekil regex sorgularını anında yakalar (Örn: *toplam profil sayısı*, *sektör sayısı*).
- **`code_interpreter` (2. Aşama)**: Çoklu filtreler, groupby, oran (%), ortalama, dağılım, sıralama veya dinamik analitik hesaplama gerektiren soruları Pandas Sandbox'a yönlendirir.
- **`semantic_rag` (3. Aşama)**: `fieldGuide`, şema tanımları, PDF, DOCX ve metin dokümanları üzerinden kavramsal soruları Hibrit Vektör + BM25 aramasına devreder.

### 2. AST Tabanlı Güvenli Sandbox ([`sandbox.py`](file:///c:/Users/merve/Desktop/rag_project/sandbox.py))
- **AST Güvenlik Analizi**: Kod derlenmeden önce Abstract Syntax Tree üzerinde taranarak `import`, `open`, `eval`, `exec`, `os`, `sys`, `subprocess` ve dunder (`__`) öznitelik erişimleri engellenir.
- **Kısıtlı Builtin Ortamı**: Yalnızca güvenli matematiksel ve yerleşik fonksiyonlar (`len`, `sum`, `range`, `min`, `max` vb.) aktiftir.
- **Kopya DataFrame İzolasyonu**: Orijinal veri setinin mutasyona uğramaması için `df.copy()` üzerinde çalışır.
- **Cross-Platform Timeout**: Windows ve Linux uyumlu `daemon thread` ile 5 saniye limitli kilitlenme koruması sağlanır.

### 3. Şema Tabanlı Kod Üretimi & Retry Döngüsü ([`code_interpreter.py`](file:///c:/Users/merve/Desktop/rag_project/code_interpreter.py))
- **Dinamik Şema Enjeksiyonu**: Yüklenen DataFrame'in sütun listesi, veri tipleri (`dtypes`) ve örnek satırları LLM prompt'una otomatik eklenir (Kolon uydurma engellenir).
- **Self-Correction Retry Döngüsü**: Kod bir hata fırlatırsa (SyntaxError, KeyError vb.), hata mesajı ve hatalı kod LLM'e geri beslenerek 3 deneme boyunca kendini düzeltmesi sağlanır.
- **Doğal Dil Sentezleyici (`result_to_natural_language`)**: Pandas hesaplama çıktısını (Series, dict, scalar, DataFrame) sayıları değiştirmeden akıcı bir Türkçe cümleye dönüştürür.

---

## 2. Test Sonuçları

### A. İzole Sandbox Güvenlik Testleri ([`test_sandbox_step1.py`](file:///c:/Users/merve/Desktop/rag_project/test_sandbox_step1.py))
| Test Adı | Girdi | Beklenen Sonuç | Durum |
| :--- | :--- | :--- | :--- |
| **Normal Toplam** | `result = df['a'].sum()` | `60` | ✅ PASS |
| **Filtreleme & Liste** | `result = df[df['sector']=='Tech']['city'].tolist()` | `['Istanbul', 'Izmir']` | ✅ PASS |
| **Yasaklı `import`** | `import os` | `Güvenlik İhlali` | ✅ PASS |
| **Yasaklı `open()`** | `open('rag.db')` | `Güvenlik İhlali` | ✅ PASS |
| **Yasaklı `eval()`** | `eval('1+1')` | `Güvenlik İhlali` | ✅ PASS |
| **KeyError Yakalama** | `df['olmayan_kolon'].mean()` | `KeyError: 'olmayan_kolon'` | ✅ PASS |
| **Timeout (Zaman Aşımı)** | `while True: pass` | `Kod çalışma süresi aşıldı (1s)` | ✅ PASS |

---

### B. `728_profiles.json` Dinamik Sorgu Testleri

#### Soru 1: `"profileType" alanına göre kaç profil "individual" kaç profil "business" olarak sınıflandırılmıştır?`
- **Üretilen Kod**:
  ```python
  result = df[df['profileType'] == 'individual'].shape[0], df[df['profileType'] == 'business'].shape[0]
  ```
- **Ham Çıktı**: `(599, 129)` (Süre: 5.75s)
- **Doğal Dil Yanıtı**: *"ProfileType" alanına göre sınıflandırılan profillerde, 599 tane profil "individual" olarak, 129 tane profil "business" olarak sınıflandırılmıştır.*

#### Soru 2: `Veri setindeki profillerde toplam kaç farklı şehir (location.city) yer almaktadır ve en çok profile sahip ilk 3 şehir hangileridir?`
- **Üretilen Kod**:
  ```python
  result = {
      'ülkede toplam şehir sayısı': df['location.city'].nunique(),
      'en çok profile sahip ilk 3 şehir': df.groupby('location.city')['profileCode'].nunique().nlargest(3).to_dict()
  }
  ```
- **Ham Çıktı**: `{'ülkede toplam şehir sayısı': 20, 'en çok profile sahip ilk 3 şehir': {'İstanbul': 130, 'İzmir': 81, 'Ankara': 77}}` (Süre: 6.21s)
- **Doğal Dil Yanıtı**: *Veri setinde toplam 20 farklı şehir bulunur ve bu şehirlerin en çok profilde olduğu sırasıyla İstanbul (130), İzmir (81) ve Ankara (77) olarak belirlenmiştir.*

#### Soru 3: `Tüm profillerin "experience.years" alanlarına göre ortalama mesleki deneyim yılı kaçtır?`
- **Üretilen Kod**:
  ```python
  result = df['experience.years'].mean()
  ```
- **Ham Çıktı**: `11.998626373626374` (Süre: 4.19s)
- **Doğal Dil Yanıtı**: *Tüm profillerin "experience.years" alanlarına göre ortalama mesleki deneyim yılı 11.998626373626374 yıldır.*

#### Soru 4: `"appointmentSettings.autoApproveRequests" değeri true olan profillerin toplam profil sayısına oranı yüzde kaçtır?`
- **Üretilen Kod**:
  ```python
  result = (df[df['appointmentSettings.autoApproveRequests'] == True].shape[0] / df.shape[0]) * 100
  ```
- **Ham Çıktı**: `26.785714285714285` (Süre: 5.44s)
- **Doğal Dil Yanıtı**: *"appointmentSettings.autoApproveRequests" değeri true olan profillerin toplam profil sayısına oranı, yaklaşık %26.79'a eşittir.*

---

### C. `data/airports.json` (İkinci JSON - Sıfır Kural ile %100 Dinamik Testler)

#### Soru 1: `Havaalanları veri setinde toplam kaç havaalanı ve kaç farklı ülke (country) bulunmaktadır?`
- **Üretilen Kod**:
  ```python
  result = {
      'total_airports': df['code'].nunique(),
      'unique_countries': df['country'].nunique()
  }
  ```
- **Ham Çıktı**: `{'total_airports': 30, 'unique_countries': 18}` (Süre: 1.71s)
- **Doğal Dil Yanıtı**: *Havaalanları veri setinde toplam 30 havaalanı ve 18 farklı ülke bulunmaktadır.*

#### Soru 2: `Hangi ülkede kaç havaalanı bulunmaktadır ve en çok havaalanına sahip ilk 3 ülke hangileridir?`
- **Üretilen Kod**:
  ```python
  result = {
      "ülke_ve_havaalan_sayisi": df.groupby('country')['code'].count().to_dict(),
      "en_fazla_havaalan_ülkeler": df.groupby('country')['code'].nunique().sort_values(ascending=False).head(3).index.tolist()
  }
  ```
- **Ham Çıktı**: `{'ülke_ve_havaalan_sayisi': {'AE': 1, 'AU': 1, 'CA': 1, 'CN': 3, 'DE': 2, 'ES': 2, 'FR': 1, 'GB': 1, 'HK': 1, 'JP': 2, 'KR': 1, 'MX': 1, 'MY': 1, 'NL': 1, 'SG': 1, 'TH': 1, 'TR': 1, 'US': 8}, 'en_fazla_havaalan_ülkeler': ['US', 'CN', 'JP']}` (Süre: 2.40s)
- **Doğal Dil Yanıtı**: *Ülkelerdeki havaalanlarının sayısı: Amerika Birleşik Devletleri (8), Çin (3), Japonya (2). En çok havaalanına sahip ilk 3 ülke Amerika Birleşik Devletleri, Çin ve Japonya'dır.*

#### Soru 3: `En kuzeyde yer alan (en yüksek enlem / lat değerine sahip) ilk 3 havaalanının isimleri ve ülkeleri nelerdir?`
- **Üretilen Kod**:
  ```python
  result = df.loc[df['lat'].nlargest(3).index, ['name', 'country']].to_dict()
  ```
- **Ham Çıktı**: `{'name': {11: 'Amsterdam Schiphol', 6: 'London Heathrow', 12: 'Frankfurt Airport'}, 'country': {11: 'NL', 6: 'GB', 12: 'DE'}}` (Süre: 1.52s)
- **Doğal Dil Yanıtı**: *En kuzeyde yer alan ilk 3 havaalanı, sırasıyla Amsterdam Schiphol (Hollanda), London Heathrow (Birleşik Krallık) ve Frankfurt Airport (Almanya)'dır.*

#### Soru 4: `ABD ('US') ülkesindeki havaalanlarının ortalama enlem (lat) ve ortalama boylam (lon) değerleri nedir?`
- **Üretilen Kod**:
  ```python
  result = {
      'average_lat': df[df['country'] == 'US']['lat'].mean(),
      'average_lon': df[df['country'] == 'US']['lon'].mean()
  }
  ```
- **Ham Çıktı**: `{'average_lat': 35.796475, 'average_lon': -96.11265}` (Süre: 1.84s)
- **Doğal Dil Yanıtı**: *ABD'deki havaalanlarının ortalama enlemi 35.796 ve ortalama boylamı -96.113'tür.*

#### Soru 5: `Tokyo şehrinde bulunan havaalanlarının kodları (code) ve isimleri (name) nelerdir?`
- **Üretilen Kod**:
  ```python
  result = df[df['city'] == 'Tokyo'][['code', 'name']]
  ```
- **Ham Çıktı**: `HND (Tokyo Haneda), NRT (Narita International)` (Süre: 1.43s)
- **Doğal Dil Yanıtı**: *Tokyo'daki havaalanlarının kodları ve isimleri, HND koduyla Tokyo Haneda ve NRT koduyla Narita International'dir.*
