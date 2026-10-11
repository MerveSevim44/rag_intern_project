# Regresyon katman 1 — final 4 parça / bağlam karşılaştırması

Soru: 159 (semantic_rag: 133, tablosal atlanan: 26); süre 7444 sn.

| k | aday kümesi değişen | final kümesi değişen | final sırası değişen | bağlam değişen | beklenen kaynağı final'den KAYBEDEN | kazanan |
|---|---|---|---|---|---|---|
| 5 | 15 | 13 | 13 | 17 | 0 | 0 |
| 8 | 17 | 12 | 12 | 14 | 0 | 0 |

## test_stopword — hedef profil final'de (eski → yeni)

| # | k=5 | k=8 |
|---|---|---|
| 301 | 1 → 1 | 1 → 1 |
| 302 | 1 → 1 | 1 → 1 |
| 303 | 0 → 1 | 1 → 1 |
| 304 | 0 → 0 | 0 → 0 |
| 305 | 4 → 4 | 4 → 4 |
| 306 | 4 → 4 | 3 → 2 |
| 307 | 4 → 4 | 4 → 4 |
| 308 | 4 → 4 | 4 → 4 |
| 309 | 4 → 4 | 4 → 4 |
| 310 | 4 → 4 | 4 → 4 |
| 311 | 4 → 4 | 4 → 4 |
| 312 | 4 → 4 | 4 → 4 |

## Bağlamı değişen sorular (elle inceleme)

### test_1 #1 (k=5) — G4.1 dilbilgisinde VT kümesinin elemanları nelerdir?
- beklenen kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf | final aynı küme: False
- ÇIKAN: `4320` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 25 — 4.5.5. Cevap 5
- GİREN: `4313` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 18 — 4.3.4.1. Yararsız Değişken ve Kuralların Atılması

### test_1 #6 (k=5) — G4.2 dilbilgisinin uç simgeler (VT) kümesi nelerdir?
- beklenen kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf | final aynı küme: False
- ÇIKAN: `4315` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 20 — Örnek 4.7
- GİREN: `4297` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 2 — 4.BAĞLAMDAN-BAĞIMSIZ DİLBİLGİSİ

### test_1 #7 (k=5) — G4.1 dilbilgisinde S=>S*S=>S*(S)=>S*(S-S)=>v*(S-S)=>v*(v-S)=>v*(v-c) türetmesi sonunda hangi tümce elde edilmiştir?
- beklenen kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf | final aynı küme: False
- ÇIKAN: `4307` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 12 — Türetme ağacı:
- GİREN: `4308` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 13 — w =(v+c)*(v-c) soldan ve sağdan

### test_1 #11 (k=8) — Bir dilin belirgin (unambiguous) olması ne anlama gelir?
- beklenen kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf | final aynı küme: False
- ÇIKAN: `3671` 728_profiles.json $.profiles[291] — profileCode: DB-FN3EC4DT
- GİREN: `3674` 728_profiles.json $.profiles[294] — profileCode: DB-HABGHQQ3

### test_1 #29 (k=5) — Örnek 8'deki G_S.4.8.1 dilbilgisinin türettiği L_S.4.8.1 dilinde üs olarak neden 2k+1 kullanılmıştır; B=>bbBdd|C kuralı bunu nasıl sağlar?
- beklenen kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf | final aynı küme: False
- ÇIKAN: `4299` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 4 — Örnek 4.2
- GİREN: `4321` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 26 — 4.5.6. Örnek 6

### test_2 #36 (k=8) — weeklyAvailability dizisinde her gün nesnesi hangi alanları (day, active, start, end) içermektedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3971` 728_profiles.json $.profiles[591] — profileCode: DB-HYV33Z27
- ÇIKAN: `3483` 728_profiles.json $.profiles[103] — profileCode: DB-XHSX4ZHW
- GİREN: `3906` 728_profiles.json $.profiles[526] — profileCode: DB-HV2XX65Q
- GİREN: `3775` 728_profiles.json $.profiles[395] — profileCode: DB-D44RAXGA

### test_2 #40 (k=5) — location.serviceArea alanı bazı profillerde 'district, city' formatındayken bazılarında 'district / online' formatında görünmektedir; bu farkın nedeni serviceModes alanıyla nasıl ilişkilidir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3841` 728_profiles.json $.profiles[461] — profileCode: DB-ZAD9FUWP
- GİREN: `3462` 728_profiles.json $.profiles[82] — profileCode: DB-8N4HZ2NW

### test_2 #41 (k=8) — searchKeywords dizisi bir profildeki hangi diğer alanlardan (sector, occupation, services, location) türetilmiş görünmektedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `4055` 728_profiles.json $.profiles[675] — profileCode: DB-SF69P49D
- GİREN: `3776` 728_profiles.json $.profiles[396] — profileCode: DB-2MA65X8Z

### test_2 #47 (k=5) — fieldGuide bölümündeki 'publicContact' açıklaması ile örnek profillerdeki publicContact nesnesinin (phone:null, email:null) içeriği birbiriyle tutarlı mıdır?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3849` 728_profiles.json $.profiles[469] — profileCode: DB-H23AAHY7
- GİREN: `4097` 728_profiles.json $.profiles[717] — profileCode: DB-GLATFT7V

### test_2 #47 (k=8) — fieldGuide bölümündeki 'publicContact' açıklaması ile örnek profillerdeki publicContact nesnesinin (phone:null, email:null) içeriği birbiriyle tutarlı mıdır?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `4072` 728_profiles.json $.profiles[692] — profileCode: DB-N2J89RFG
- GİREN: `3694` 728_profiles.json $.profiles[314] — profileCode: DB-TEGJDSPB

### test_2 #49 (k=5) — intendedUse listesinde belirtilen 'demo', 'test', 'seed data', 'UI population' kullanım amaçları syntheticOnly=true ayarıyla nasıl bir tutarlılık göstermektedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

### test_4 #92 (k=5) — Anlatıcının Oda No: 304'ü kiraladığı şehir ve mevsim hangisidir?
- beklenen kaynak: test2.txt | final aynı küme: False
- ÇIKAN: `4202` lsarSist-H9_ZTransform.pdf sayfa 15 — Z-transform Properties
- ÇIKAN: `4301` 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa 6 — Örnek 4.4
- GİREN: `4230` test1.txt paragraf 4 — İçeri süzüldü. Merdivenler onu yerin yedi kat altına, sadece havada uçuşan kadim büyü parı
- GİREN: `4231` test1.txt paragraf 5 — Alis masaya yaklaştı ve parmaklarını defterin üzerinde gezdirdi. Dokunduğu an, odadaki tüm

### test_4 #92 (k=8) — Anlatıcının Oda No: 304'ü kiraladığı şehir ve mevsim hangisidir?
- beklenen kaynak: test2.txt | final aynı küme: False
- ÇIKAN: `4110` 728_profiles.json $.fieldGuide — displayName: Public-facing profile/business name.
- ÇIKAN: `4202` lsarSist-H9_ZTransform.pdf sayfa 15 — Z-transform Properties
- GİREN: `4230` test1.txt paragraf 4 — İçeri süzüldü. Merdivenler onu yerin yedi kat altına, sadece havada uçuşan kadim büyü parı
- GİREN: `4231` test1.txt paragraf 5 — Alis masaya yaklaştı ve parmaklarını defterin üzerinde gezdirdi. Dokunduğu an, odadaki tüm

### test_5 #115 (k=5) — Oda No: 304 hikayesinde anlatıcının mesleği nedir?
- beklenen kaynak: - | final aynı küme: False
- ÇIKAN: `3882` 728_profiles.json $.profiles[502] — profileCode: DB-PXXVR69C
- GİREN: `3868` 728_profiles.json $.profiles[488] — profileCode: DB-MHD5CC83

### test_negative #207 (k=8) — Wavelet dönüşümünün zaman-frekans çözünürlüğü avantajı nedir?
- beklenen kaynak: - | final aynı küme: False
- ÇIKAN: `4176` lsarSist-H8_FourierTransform.pdf sayfa 3 — Sürekli Zamanlı Fourier Dönüşümü
- GİREN: `3975` 728_profiles.json $.profiles[595] — profileCode: DB-9EQALXAT

### test_negative #220 (k=8) — Summer School planında ikinci ay için ayrılan bütçe ne kadardır?
- beklenen kaynak: - | final aynı küme: False
- ÇIKAN: `4068` 728_profiles.json $.profiles[688] — profileCode: DB-DWBPFJSL
- GİREN: `3709` 728_profiles.json $.profiles[329] — profileCode: DB-3H36XTSG

### test_negative #229 (k=5) — Summer School programının 2027 yılı kayıt takvimi nasıldır?
- beklenen kaynak: - | final aynı küme: False
- ÇIKAN: `4072` 728_profiles.json $.profiles[692] — profileCode: DB-N2J89RFG
- GİREN: `3714` 728_profiles.json $.profiles[334] — profileCode: DB-Q4GPF7QR

### test_negative #229 (k=8) — Summer School programının 2027 yılı kayıt takvimi nasıldır?
- beklenen kaynak: - | final aynı küme: False
- ÇIKAN: `4072` 728_profiles.json $.profiles[692] — profileCode: DB-N2J89RFG
- ÇIKAN: `4069` 728_profiles.json $.profiles[689] — profileCode: DB-UN35VXFG
- GİREN: `3713` 728_profiles.json $.profiles[333] — profileCode: DB-GVYPCWHM
- GİREN: `3692` 728_profiles.json $.profiles[312] — profileCode: DB-TWC5P2ER

### test_stopword #301 (k=5) — Damla Akın hangi şehirde hizmet veriyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `4069` 728_profiles.json $.profiles[689] — profileCode: DB-UN35VXFG
- ÇIKAN: `3596` 728_profiles.json $.profiles[216] — profileCode: DB-B7FM64VP
- ÇIKAN: `3794` 728_profiles.json $.profiles[414] — profileCode: DB-4P4YBAWX
- GİREN: `3402` 728_profiles.json $.profiles[22] — profileCode: DB-H55U4HRR
- GİREN: `4017` 728_profiles.json $.profiles[637] — profileCode: DB-GMUWZRJM
- GİREN: `3405` 728_profiles.json $.profiles[25] — profileCode: DB-ZMNNBZLB

### test_stopword #301 (k=8) — Damla Akın hangi şehirde hizmet veriyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `4069` 728_profiles.json $.profiles[689] — profileCode: DB-UN35VXFG
- ÇIKAN: `3536` 728_profiles.json $.profiles[156] — profileCode: DB-ADLRQWTL
- ÇIKAN: `3596` 728_profiles.json $.profiles[216] — profileCode: DB-B7FM64VP
- GİREN: `3402` 728_profiles.json $.profiles[22] — profileCode: DB-H55U4HRR
- GİREN: `4017` 728_profiles.json $.profiles[637] — profileCode: DB-GMUWZRJM
- GİREN: `3804` 728_profiles.json $.profiles[424] — profileCode: DB-HQF289U4

### test_stopword #302 (k=5) — Deniz Akın'ın mesleği nedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3483` 728_profiles.json $.profiles[103] — profileCode: DB-XHSX4ZHW
- GİREN: `3846` 728_profiles.json $.profiles[466] — profileCode: DB-YWCZEXFU

### test_stopword #302 (k=8) — Deniz Akın'ın mesleği nedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3414` 728_profiles.json $.profiles[34] — profileCode: DB-NGT7HW4J
- GİREN: `3749` 728_profiles.json $.profiles[369] — profileCode: DB-QUBW649X

### test_stopword #303 (k=5) — Deniz Çelik hangi hizmetleri sunuyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3511` 728_profiles.json $.profiles[131] — profileCode: DB-7VBBCP8Y
- GİREN: `3625` 728_profiles.json $.profiles[245] — profileCode: DB-WMDRZ666

### test_stopword #303 (k=8) — Deniz Çelik hangi hizmetleri sunuyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3727` 728_profiles.json $.profiles[347] — profileCode: DB-P4E4HHR6
- GİREN: `3749` 728_profiles.json $.profiles[369] — profileCode: DB-QUBW649X

### test_stopword #304 (k=5) — Ön değerlendirme hizmeti hangi meslekteki uzmanlar tarafından veriliyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

### test_stopword #304 (k=8) — Ön değerlendirme hizmeti hangi meslekteki uzmanlar tarafından veriliyor?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

### test_stopword #306 (k=5) — İş modeli görüşmesi sunan danışmanların mesleği nedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

### test_stopword #306 (k=8) — İş modeli görüşmesi sunan danışmanların mesleği nedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3848` 728_profiles.json $.profiles[468] — profileCode: DB-H9FS2CS7
- GİREN: `3833` 728_profiles.json $.profiles[453] — profileCode: DB-XZLFAE9V

### test_stopword #309 (k=5) — Çevrim içi Türkçe dersi veren eğitmenlerin mesleği nedir?
- beklenen kaynak: 728_profiles.json | final aynı küme: False
- ÇIKAN: `3723` 728_profiles.json $.profiles[343] — profileCode: DB-VQ83W3RL
- GİREN: `3716` 728_profiles.json $.profiles[336] — profileCode: DB-XJDECP7D

### test_stopword #312 (k=5) — Girişimcilik ve iş geliştirme deneyimi olan uzmanlar hangi meslekte?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

### test_stopword #312 (k=8) — Girişimcilik ve iş geliştirme deneyimi olan uzmanlar hangi meslekte?
- beklenen kaynak: 728_profiles.json | final aynı küme: True
- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)

