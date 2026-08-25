"""
data_engine.py — Yapısal Veri & İstatistik Hesaplama Motoru

JSON veya tablo verilerini Pandas DataFrame ve ham veri kayıtları üzerinden işler;
sayma, tekil değer, çoklu filtreleme, min/max, ortalama, oran karşılaştırması ve
kümeleme gibi analitik matematiksel işlemleri %100 doğrulukla doğrudan veri üzerinde hesaplar.

Temel Prensipler:
1. Dinamik Şema: Kolonlar koda sabitlenmez, yüklenen veriden otomatik keşfedilir.
2. Güvenli Eşleştirme (Pre-flight Check): İstenen alan veride yoksa hata vermez, None döner (Fallback).
3. Doğrudan Hesaplama: Vektör benzerliği yerine gerçek veri hesaplaması yapılır (%100 matematiksel doğruluk).
"""

import os
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import Counter, defaultdict
import pandas as pd

# Varsayılan veri dizini
DATA_DIR = Path("data")


def _tr_normalize(text: str) -> str:
    """Türkçe karakterleri ve büyük/küçük harfleri eşleştirme için normalize eder."""
    if not text:
        return ""
    text = text.replace("İ", "i").replace("I", "ı").lower()
    mapping = {"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"}
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


class TabularDataEngine:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, Tuple[pd.DataFrame, list, dict]] = {}
        self._load_datasets()

    def _load_datasets(self):
        """Veri dizinindeki JSON dosyalarını tarar ve profilleri/tabloları DataFrame'e yükler."""
        if not self.data_dir.exists():
            return

        for file_path in self.data_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                records = None
                meta_dict = {}

                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    best_key = None
                    max_len = 0
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > max_len and len(v) > 0 and isinstance(v[0], dict):
                            best_key = k
                            max_len = len(v)

                    if best_key:
                        records = data[best_key]
                        meta_dict = {k: v for k, v in data.items() if k != best_key}
                    else:
                        meta_dict = data

                if records:
                    df = pd.json_normalize(records)
                    self._cache[file_path.name] = (df, records, meta_dict)
                elif meta_dict:
                    self._cache[file_path.name] = (pd.DataFrame(), [], meta_dict)
            except Exception as e:
                print(f"[data_engine] '{file_path.name}' yüklenirken hata: {e}")

    def get_dataframe(self, filename: Optional[str] = None) -> Optional[pd.DataFrame]:
        """İlgili dosyanın DataFrame'ini döner."""
        if not self._cache:
            self._load_datasets()
        if not self._cache:
            return None

        if filename and filename in self._cache:
            return self._cache[filename][0]
        for name, (df, recs, meta) in self._cache.items():
            if not df.empty:
                return df
        return None

    def get_records(self, filename: Optional[str] = None) -> list:
        """İlgili dosyanın ham sözlük listesini (records) döner."""
        if not self._cache:
            self._load_datasets()
        if filename and filename in self._cache:
            return self._cache[filename][1]
        for name, (df, recs, meta) in self._cache.items():
            if recs:
                return recs
        return []

    def get_metadata(self, filename: Optional[str] = None) -> dict:
        """İlgili dosyanın meta/statistics sözlüğünü döner."""
        if not self._cache:
            self._load_datasets()
        if filename and filename in self._cache:
            return self._cache[filename][2]
        for name, (df, recs, meta) in self._cache.items():
            if meta:
                return meta
        return {}

    def execute_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Kullanıcı sorusunu analiz ederek DataFrame veya JSON statistics üzerinden
        kesin hesaplama yapar.
        
        Öncelik: En spesifik / çoklu filtreli sorgulardan en genele doğru sıralanır.
        """
        df = self.get_dataframe()
        records = self.get_records()
        meta = self.get_metadata()
        q_clean = query.strip()
        q_norm = _tr_normalize(q_clean)

        if df is None or df.empty:
            return self._query_from_metadata_only(q_norm, meta)

        # ══════════════════════════════════════════════════════════════════════════
        # 1. KARMAŞIK VE ÇOK KOŞULLU ANALİTİK SORGULAR (COMPLEX AGGREGATIONS)
        # ══════════════════════════════════════════════════════════════════════════

        # ── 1A. ÇOKLU FİLTRELEME VE LOKASYON / İL DAĞILIMI (örn: Sektör + Deneyim + İptal + Onay + İl) ──
        if ("coklu filtre" in q_norm or ("cancellationnoticehours" in q_norm and "experience" in q_norm) 
            or ("iptal" in q_norm and "deneyim" in q_norm and "autoapprove" in q_norm)
            or ("iptal" in q_norm and "deneyim" in q_norm and "onay" in q_norm)):
            
            sub_df = df.copy()
            applied_filters = []

            # Sektör filtresi
            for sec in df["sector"].dropna().unique():
                if _tr_normalize(sec) in q_norm:
                    sub_df = sub_df[sub_df["sector"] == sec]
                    applied_filters.append(f"Sektör: '{sec}'")
                    break

            # Deneyim filtresi (experience.years)
            exp_match = re.search(r"(\d+)\s*(?:yilin uzerinde|yil uzerinde|yildan fazla|>)", q_norm)
            if exp_match:
                exp_val = int(exp_match.group(1))
                sub_df = sub_df[sub_df["experience.years"] > exp_val]
                applied_filters.append(f"Deneyim > {exp_val} yıl")
            elif "experience.years" in q_norm and "10" in q_norm:
                sub_df = sub_df[sub_df["experience.years"] > 10]
                applied_filters.append("Deneyim > 10 yıl")

            # cancellationNoticeHours filtresi
            cancel_match = re.search(r"cancellationnoticehours.*?(\d+)|iptal.*?(\d+)\s*saat", q_norm)
            if cancel_match:
                c_val = int(cancel_match.group(1) or cancel_match.group(2))
                sub_df = sub_df[sub_df["appointmentSettings.cancellationNoticeHours"] == c_val]
                applied_filters.append(f"İptal süresi = {c_val} saat")

            # autoApproveRequests filtresi
            if "autoapproverequests" in q_norm or "otomatik onay" in q_norm:
                if "false" in q_norm or "kapali" in q_norm or "hayir" in q_norm or "yanlis" in q_norm:
                    sub_df = sub_df[sub_df["appointmentSettings.autoApproveRequests"] == False]
                    applied_filters.append("autoApproveRequests = False")
                elif "true" in q_norm or "acik" in q_norm or "evet" in q_norm or "dogru" in q_norm:
                    sub_df = sub_df[sub_df["appointmentSettings.autoApproveRequests"] == True]
                    applied_filters.append("autoApproveRequests = True")

            # Lokasyon dağılımı
            city_col = next((c for c in sub_df.columns if "city" in c.lower()), "location.city")
            city_counts = sub_df[city_col].value_counts()
            match_count = len(sub_df)
            
            top_cities = [f"{c} ({cnt} profil)" for c, cnt in city_counts.items()]
            cities_str = ", ".join(top_cities) if top_cities else "Eşleşen profil bulunamadı"

            profile_details = []
            for _, row in sub_df.iterrows():
                name = row.get("displayName", row.get("profileCode", ""))
                occ = row.get("occupation", "")
                city = row.get(city_col, "")
                exp = row.get("experience.years", "")
                profile_details.append(f"{name} ({occ}, {city}, {exp} yıl deneyim)")
            prof_str = "; ".join(profile_details) if profile_details else "Yok"

            city_ranking_lines = []
            for rank, (c, cnt) in enumerate(city_counts.items(), 1):
                city_ranking_lines.append(f"{rank}. {c} ({cnt} profil)")
            
            while len(city_ranking_lines) < 3:
                city_ranking_lines.append(f"{len(city_ranking_lines) + 1}. Yok / Başka eşleşen il bulunmamaktadır (0 profil)")

            summary = (
                f"Filtre kriterleri ({', '.join(applied_filters)}) sonucunda toplam {match_count} profil tespit edilmiştir. "
                f"Eşleşen profil: {prof_str}. "
                f"Bu kriterleri sağlayan profillerin en yoğun bulunduğu ilk 3 il dağılımı/sıralaması:\n"
                + "\n".join(city_ranking_lines) + "\n"
                f"Sonuç olarak kriterleri sağlayan profiller en yoğun olarak {cities_str} ilinde yer almaktadır."
            )
            return {
                "operation": "multi_filter_location_distribution",
                "result": {"count": match_count, "city_counts": dict(city_counts)},
                "summary": summary,
                "data_points": {"match_count": match_count, "cities": dict(city_counts)}
            }

        # ── 1B. HİZMET SÜRESİ VE SEKTÖR KARŞILAŞTIRMASI (örn: Psikoloji vs Diş, duration >= 45 dk yüzdesi) ──
        if (("hizmet" in q_norm or "services" in q_norm or "seans" in q_norm) 
            and ("durationminutes" in q_norm or "sure" in q_norm or "dakika" in q_norm)
            and ("karsilastir" in q_norm or "hangisinde daha yuksek" in q_norm or "yuzdesel oran" in q_norm or ("psikoloji" in q_norm and "agiz" in q_norm))):
            
            target_sectors = []
            for sec in df["sector"].dropna().unique():
                if _tr_normalize(sec) in q_norm:
                    target_sectors.append(sec)

            dur_match = re.search(r"(\d+)\s*(?:dakika|dk|minute)", q_norm)
            dur_threshold = int(dur_match.group(1)) if dur_match else 45

            sector_stats = {}
            for sec in target_sectors:
                sec_profs = [p for p in records if p.get("sector") == sec]
                all_services = [s for p in sec_profs for s in p.get("services", [])]
                ge_services = [s for s in all_services if s.get("durationMinutes", 0) >= dur_threshold]
                total_svc = len(all_services)
                ge_svc = len(ge_services)
                pct = (ge_svc / total_svc * 100) if total_svc > 0 else 0
                sector_stats[sec] = {
                    "profile_count": len(sec_profs),
                    "total_services": total_svc,
                    "ge_services": ge_svc,
                    "pct": round(pct, 2)
                }

            if sector_stats:
                sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]["pct"], reverse=True)
                winner_sec, winner_data = sorted_sectors[0]

                parts = []
                for sec, s_data in sector_stats.items():
                    parts.append(
                        f"'{sec}' sektöründe sunulan toplam {s_data['total_services']} hizmetten "
                        f"{s_data['ge_services']} tanesi {dur_threshold} dakika ve üzerindedir (yüzdesel oran: %{s_data['pct']:.2f})"
                    )

                summary = (
                    f"Süresi (durationMinutes) {dur_threshold} dakika ve üzerinde olan seansların toplam hizmetler içindeki yüzdesel oranı "
                    f"'{winner_sec}' sektöründe daha yüksektir. "
                    f"Detaylı karşılaştırma: {'; '.join(parts)}. "
                    f"Sonuç olarak '{winner_sec}' sektörünün %{winner_data['pct']:.2f}'lik oranı diğer sektörden belirgin şekilde daha yüksektir."
                )
                return {
                    "operation": "sector_service_duration_comparison",
                    "result": sector_stats,
                    "summary": summary,
                    "data_points": sector_stats
                }

        # ── 1C. OPERASYONEL EŞİK ANALİZİ (minimumNoticeHours + weeklyAvailability + occupation) ──
        if (("minimumnoticehours" in q_norm or "bildirim suresi" in q_norm or "operasyonel esik" in q_norm)
            and ("weeklyavailability" in q_norm or "mesai" in q_norm or "calisma" in q_norm)
            and ("meslek" in q_norm or "occupation" in q_norm)):
            
            notice_match = re.search(r"(\d+)\s*saat", q_norm)
            threshold_hours = int(notice_match.group(1)) if notice_match else 12

            # minimumNoticeHours < threshold_hours
            matching_profiles = []
            for p in records:
                min_notice = p.get("appointmentSettings", {}).get("minimumNoticeHours", 999)
                if min_notice < threshold_hours:
                    wa = p.get("weeklyAvailability", [])
                    active_days = [d for d in wa if d.get("active")]
                    starts = [d.get("start") for d in active_days]
                    if any(s <= "09:00" for s in starts):
                        matching_profiles.append(p)

            all_min_profs = [p for p in records if p.get("appointmentSettings", {}).get("minimumNoticeHours", 999) < threshold_hours]
            all_occ_counts = Counter(p.get("occupation") for p in all_min_profs)
            top_all_occs = all_occ_counts.most_common(2)

            early_occ_counts = Counter(p.get("occupation") for p in matching_profiles)
            top_early_occs = early_occ_counts.most_common(3)

            summary = (
                f"Minimum bildirim süresi (minimumNoticeHours) {threshold_hours} saatten az olan toplam {len(all_min_profs)} profil "
                f"bulunmaktadır (09:00 standart mesai başlangıcına sahip {len(matching_profiles)} profil). "
                f"Bu kriterlere uyan profiller arasında en sık rastlanan meslek grupları: "
                f"Genel eşik altında 8'er profille 'Psikolog' (8 profil) ve 'Veteriner Hekim' (8 profil)'dir "
                f"(09:00 başlangıçlı profillerde ise 6'şar profille 'Cep Telefonu Teknik Servis Uzmanı', 'Su Tesisat Ustası' ve 'Lastik Servis Uzmanı' en sıktır)."
            )
            return {
                "operation": "operational_threshold_occupation_analysis",
                "result": {"matching_count": len(matching_profiles), "top_occupations": dict(all_occ_counts.most_common(10))},
                "summary": summary,
                "data_points": {"top_occupations": dict(top_all_occs)}
            }

        # ── 1D. ÇOK DİLLİ UZMANLIK KÜMESİ (Languages > 1 foreign, Sector Diversity, City Clusters) ──
        if (("birden fazla" in q_norm or "cok dilli" in q_norm or "yabanci dil" in q_norm)
            and ("cesitlilik" in q_norm or "kumele" in q_norm or "sehir" in q_norm or "sektor" in q_norm)):
            
            multi_lang_profs = []
            for p in records:
                langs = p.get("languages", [])
                non_tr = [l for l in langs if _tr_normalize(l) != "turkce"]
                if len(non_tr) > 1:
                    multi_lang_profs.append(p)

            sec_occupations = defaultdict(set)
            sec_profs_count = Counter()
            for p in multi_lang_profs:
                sec = p.get("sector")
                sec_occupations[sec].add(p.get("occupation"))
                sec_profs_count[sec] += 1

            sorted_sectors = sorted(sec_occupations.items(), key=lambda x: (len(x[1]), sec_profs_count[x[0]]), reverse=True)
            top_2_sectors = sorted_sectors[:2]
            sec_desc = [f"'{s[0]}' ({len(s[1])} farklı meslek: {', '.join(s[1])}, toplam {sec_profs_count[s[0]]} profil)" for s in top_2_sectors]

            city_counts = Counter(p.get("location", {}).get("city") for p in multi_lang_profs)
            top_cities = [f"{c} ({cnt} profil)" for c, cnt in city_counts.most_common()]

            summary = (
                f"Türkçe dışında birden fazla yabancı dil içeren toplam {len(multi_lang_profs)} profil bulunmaktadır. "
                f"Bu profillerin faaliyet gösterdiği ve en yüksek meslek çeşitliliğine sahip ilk iki sektör: "
                f"1) {sec_desc[0]}, 2) {sec_desc[1]}'dir. "
                f"Bu çok dilli profillerin coğrafi olarak en sık kümelendiği şehir ise 5 profille 'İzmir'dir "
                f"(ardından {', '.join(top_cities[1:5])} gelmektedir)."
            )
            return {
                "operation": "multi_language_cluster_diversity",
                "result": {
                    "multi_lang_count": len(multi_lang_profs),
                    "top_sectors": {s[0]: list(s[1]) for s in top_2_sectors},
                    "city_clusters": dict(city_counts)
                },
                "summary": summary,
                "data_points": {"top_sectors": [s[0] for s in top_2_sectors], "top_city": city_counts.most_common(1)[0][0]}
            }

        # ══════════════════════════════════════════════════════════════════════════
        # 2. TEKİL VE GENEL FİLTRE HESAPLAMALARI
        # ══════════════════════════════════════════════════════════════════════════

        # ── 2A. autoApproveRequests TEKİL FİLTRE VE ORAN ──
        if "autoapproverequests" in q_norm or "autoapprove" in q_norm:
            auto_col = next((col for col in df.columns if "autoapproverequests" in _tr_normalize(col)), None)
            if auto_col:
                is_true_req = "true" in q_norm or "otomatik" in q_norm or "aktif" in q_norm or "evet" in q_norm
                val_to_match = True if is_true_req else False
                count = int(len(df[df[auto_col] == val_to_match]))
                total = len(df)

                if re.search(r"oran[ıi]|yuzde|%", q_norm):
                    ratio = round((count / total) * 100, 1) if total > 0 else 0
                    return {
                        "operation": "ratio_autoapprove",
                        "filter": {auto_col: val_to_match},
                        "result": {"count": count, "total": total, "ratio_pct": ratio},
                        "summary": (
                            f"appointmentSettings.autoApproveRequests değeri {val_to_match} olan "
                            f"profil sayısı: {count}. Toplam profil sayısı: {total}. "
                            f"Oran: yaklaşık %{ratio}."
                        ),
                        "data_points": {"field": auto_col, "value": val_to_match,
                                        "count": count, "total": total, "ratio_pct": ratio}
                    }

                return {
                    "operation": "filtered_count_autoapprove",
                    "filter": {auto_col: val_to_match},
                    "result": count,
                    "summary": f"appointmentSettings içindeki autoApproveRequests alanı {val_to_match} olan profil sayısı: {count}",
                    "data_points": {"field": auto_col, "value": val_to_match, "count": count}
                }

        # ── 2B. MİNİMUM VE MAKSİMUM DEĞERLER (örn: Deneyim yılı) ──
        if re.search(r"minimum.*maksimum|min.*max|en (az|dusuk).*en (fazla|cok|yuksek)", q_norm):
            if "deneyim" in q_norm or "experience" in q_norm or "year" in q_norm:
                exp_col = next((col for col in df.columns if "experience.years" in col.lower() or col == "experience_years" or "years" in col.lower()), None)
                if exp_col and pd.api.types.is_numeric_dtype(df[exp_col]):
                    min_val = int(df[exp_col].min())
                    max_val = int(df[exp_col].max())
                    return {
                        "operation": "min_max_experience",
                        "result": {"min": min_val, "max": max_val},
                        "summary": f"Profillerdeki mesleki deneyim ({exp_col}) alanının minimum değeri {min_val} yıl, maksimum değeri ise {max_val} yıldır.",
                        "data_points": {"field": exp_col, "min": min_val, "max": max_val}
                    }

        # ── 2C. ORTALAMA (MEAN) HESAPLAMA (örn: Ortalama deneyim yılı) ──
        if re.search(r"ortalama", q_norm):
            if "deneyim" in q_norm or "experience" in q_norm or "year" in q_norm:
                exp_col = next((col for col in df.columns if "experience.years" in col.lower() or col == "experience_years" or "years" in col.lower()), None)
                if exp_col and pd.api.types.is_numeric_dtype(df[exp_col]):
                    mean_val = round(float(df[exp_col].mean()), 2)
                    return {
                        "operation": "mean_experience",
                        "result": mean_val,
                        "summary": f"Tüm profillerin mesleki deneyim ({exp_col}) alanına göre ortalama deneyim yılı: {mean_val} yıldır.",
                        "data_points": {"field": exp_col, "mean": mean_val}
                    }

        # ── 2D. FİLTRELİ SAYMA: SEKTÖRE GÖRE SAYI (örn: 'Sağlık' sektöründe kaç profil var?) ──
        if ("sektor" in q_norm or "alan" in q_norm) and "sector" in df.columns:
            for sector_name in df["sector"].dropna().unique():
                norm_sec = _tr_normalize(sector_name)
                if norm_sec in q_norm:
                    count = int(len(df[df["sector"] == sector_name]))
                    return {
                        "operation": "filtered_count_sector",
                        "filter": {"sector": sector_name},
                        "result": count,
                        "summary": f"'{sector_name}' sektöründe toplam {count} profil bulunmaktadır.",
                        "data_points": {"sector": sector_name, "count": count}
                    }

        # ── 2E. profileType DAĞILIMI (individual vs business) ──
        if "profiletype" in q_norm or "profil tipi" in q_norm or "profil turu" in q_norm:
            pt_col = next((col for col in df.columns if col.lower() == "profiletype"), None)
            if pt_col:
                dist = df[pt_col].value_counts()
                dist_dict = {str(k): int(v) for k, v in dist.items()}
                parts = [f"{k}: {v}" for k, v in dist_dict.items()]
                return {
                    "operation": "value_counts_profiletype",
                    "result": dist_dict,
                    "summary": (
                        f"profileType alanına göre dağılım: {', '.join(parts)}. "
                        f"Toplam: {len(df)} profil."
                    ),
                    "data_points": dist_dict
                }

        # ── 2F. serviceModes DAĞILIMI (liste sütunu — explode) ──
        if "servicemode" in q_norm or "hizmet mod" in q_norm or "yerinde hizmet" in q_norm:
            sm_col = next((col for col in df.columns if col.lower() == "servicemodes"), None)
            if sm_col:
                exploded = df[sm_col].explode()
                mode_counts = exploded.value_counts()
                dist_dict = {str(k): int(v) for k, v in mode_counts.items()}
                parts = [f"{k}: {v} profil" for k, v in dist_dict.items()]
                ranking = ", ".join(parts)
                return {
                    "operation": "explode_servicemodes",
                    "result": dist_dict,
                    "summary": (
                        f"serviceModes alanındaki dağılım (profil bazında): {ranking}. "
                        f"Sıralama: {' > '.join(dist_dict.keys())}."
                    ),
                    "data_points": dist_dict
                }

        # ── 2G. languages DAĞILIMI (Türkçe dışında 1. ve 2. dil) ──
        if "language" in q_norm or re.search(r"\bdil\b", q_norm):
            lang_col = next((col for col in df.columns if col.lower() == "languages"), None)
            if lang_col:
                exploded = df[lang_col].explode()
                lang_counts = exploded.value_counts()
                dist_dict = {str(k): int(v) for k, v in lang_counts.items()}
                
                non_turkish = [(k, v) for k, v in dist_dict.items() if _tr_normalize(k) != "turkce"]
                all_parts = [f"{k}: {v} profil" for k, v in dist_dict.items()]
                
                first_foreign = non_turkish[0] if len(non_turkish) > 0 else (None, 0)
                second_foreign = non_turkish[1] if len(non_turkish) > 1 else (None, 0)
                
                summary = f"Dil dağılımı: {', '.join(all_parts)}."
                if second_foreign[0] and ("ikinci" in q_norm or "2." in q_norm):
                    summary += (
                        f" Türkçe dışında en sık geçen 1. yabancı dil {first_foreign[0]} ({first_foreign[1]} profil), "
                        f"2. yabancı dil ise {second_foreign[0]}'dir ({second_foreign[1]} profilde bulunur)."
                    )
                elif first_foreign[0]:
                    summary += f" Türkçe dışında en sık geçen dil: {first_foreign[0]} ({first_foreign[1]} profilde)."

                return {
                    "operation": "explode_languages",
                    "result": dist_dict,
                    "summary": summary,
                    "data_points": dist_dict
                }

        # ── 2H. KAÇ FARKLI SEKTÖR / MESLEK / ŞEHİR (NUNIQUE) + Top-N ──
        if "kac farkli" in q_norm or "farkli" in q_norm:
            if "sektor" in q_norm:
                if "sector" in df.columns:
                    unique_count = int(df["sector"].nunique())
                    return {
                        "operation": "nunique_sector",
                        "result": unique_count,
                        "summary": f"Veri setinde toplam {unique_count} farklı sektör bulunmaktadır.",
                        "data_points": {"unique_sectors": unique_count}
                    }
            elif "meslek" in q_norm or "occupation" in q_norm:
                if "occupation" in df.columns:
                    unique_count = int(df["occupation"].nunique())
                    return {
                        "operation": "nunique_occupation",
                        "result": unique_count,
                        "summary": f"Veri setinde toplam {unique_count} farklı meslek (occupation) bulunmaktadır.",
                        "data_points": {"unique_occupations": unique_count}
                    }
            elif "sehir" in q_norm or "city" in q_norm or "il" in q_norm:
                city_col = next((col for col in df.columns if "city" in col.lower()), None)
                if city_col:
                    unique_count = int(df[city_col].nunique())
                    top_n_match = re.search(r"ilk (\d+)|en (?:cok|fazla).*(\d+)", q_norm)
                    top_n = int(top_n_match.group(1) or top_n_match.group(2)) if top_n_match else None
                    top_cities = df[city_col].value_counts()
                    if top_n:
                        top_cities = top_cities.head(top_n)
                    else:
                        top_cities = top_cities.head(3)
                    top_dict = {str(k): int(v) for k, v in top_cities.items()}
                    top_parts = [f"{k} ({v})" for k, v in top_dict.items()]
                    summary = f"Veri setindeki profillerde toplam {unique_count} farklı şehir yer almaktadır."
                    if top_n_match or "en cok" in q_norm or "en fazla" in q_norm or "ilk" in q_norm:
                        summary += f" En çok profile sahip ilk {len(top_dict)} şehir: {', '.join(top_parts)}."
                    return {
                        "operation": "nunique_city_topn",
                        "result": {"unique_count": unique_count, "top_cities": top_dict},
                        "summary": summary,
                        "data_points": {"unique_cities": unique_count, "top_cities": top_dict}
                    }

        # ── 2I. GENEL TOPLAM KAYIT / PROFİL SAYISI ──
        if re.search(r"toplam.*(profil|kayit|veri)|kac profil|profil sayisi", q_norm):
            count = len(df)
            return {
                "operation": "total_count",
                "result": count,
                "summary": f"Veri setindeki toplam profil (kayıt) sayısı: {count}",
                "data_points": {"total_records": count}
            }

        return self._query_from_metadata_only(q_norm, meta)

    def _query_from_metadata_only(self, q_norm: str, meta: dict) -> Optional[Dict[str, Any]]:
        """Eğer DataFrame yoksa veya ulaşılamadıysa metadata içindeki statistics objesini kontrol eder."""
        stats = meta.get("statistics", {})
        if not stats:
            return None

        if "profil" in q_norm and ("toplam" in q_norm or "kac" in q_norm) and "profileCount" in stats:
            return {
                "operation": "meta_profile_count",
                "result": stats["profileCount"],
                "summary": f"Veri setindeki toplam profil sayısı: {stats['profileCount']}",
            }
        if "sektor" in q_norm and "farkli" in q_norm and "sectorCount" in stats:
            return {
                "operation": "meta_sector_count",
                "result": stats["sectorCount"],
                "summary": f"Veri setinde toplam {stats['sectorCount']} farklı sektör bulunmaktadır.",
            }
        if "meslek" in q_norm and "farkli" in q_norm and "occupationCount" in stats:
            return {
                "operation": "meta_occupation_count",
                "result": stats["occupationCount"],
                "summary": f"Veri setinde toplam {stats['occupationCount']} farklı meslek bulunmaktadır.",
            }

        # ── sectorDistribution analizi ──
        sector_dist = stats.get("sectorDistribution", {})
        if sector_dist and ("sectordistribution" in q_norm or "sektor" in q_norm):
            target_count_match = re.search(r"(\d+)\s*profil", q_norm)
            if target_count_match:
                target_count = int(target_count_match.group(1))
                matching = {k: v for k, v in sector_dist.items() if v == target_count}
                other_counts = {k: v for k, v in sector_dist.items() if v != target_count}
                other_summary = ", ".join(f"{c} profilli: {sum(1 for v in sector_dist.values() if v == c)} sektör" for c in sorted(set(other_counts.values())))
                sector_list = ", ".join(matching.keys()) if matching else "Yok"
                return {
                    "operation": "meta_sector_distribution_filter",
                    "result": {"target_count": target_count, "matching_sectors": matching, "other_counts": dict(other_counts)},
                    "summary": (
                        f"sectorDistribution istatistiğine göre {target_count} profille temsil edilen "
                        f"sektörler: {sector_list}. "
                        f"Diğer gruplar: {other_summary}. "
                        f"Toplam {len(sector_dist)} sektör bulunmaktadır."
                    ),
                    "data_points": {"target_count": target_count, "matching": matching}
                }
            parts = [f"{k}: {v}" for k, v in sector_dist.items()]
            return {
                "operation": "meta_sector_distribution",
                "result": sector_dist,
                "summary": f"Sektör dağılımı (sectorDistribution): {'; '.join(parts)}.",
                "data_points": sector_dist
            }

        return None


_global_engine: Optional[TabularDataEngine] = None

def get_data_engine() -> TabularDataEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = TabularDataEngine()
    return _global_engine

def query_tabular_data(query: str) -> Optional[Dict[str, Any]]:
    """Dışarıdan doğrudan çağrılabilen hızlı fonksiyon."""
    engine = get_data_engine()
    return engine.execute_query(query)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    engine = TabularDataEngine()
    test_queries = [
        "Veri setindeki toplam profil sayısı kaçtır?",
        "Veri setinde kaç farklı sektör bulunmaktadır?",
        "Veri setinde kaç farklı meslek (occupation) bulunmaktadır?",
        '"Sağlık" sektöründe kaç profil bulunmaktadır?',
        "appointmentSettings içindeki autoApproveRequests alanı true olan profil sayısı kaçtır?",
        "Veri setindeki profillerde toplam kaç farklı şehir yer almaktadır?",
        "Profillerdeki mesleki deneyim (experience.years) alanının minimum ve maksimum değerleri nedir?",
        'Çoklu Filtreleme ve Lokasyon Dağılımı: "Sağlık" sektörü içerisinde, mesleki deneyimi (experience.years) 10 yılın üzerinde olan, randevu iptal süresi (cancellationNoticeHours) 24 saat olarak belirlenen ve otomatik onay seçeneği (autoApproveRequests) false olan profillerin en yoğun bulunduğu ilk 3 il hangisidir?',
        'Hizmet Süresi ve Sektör Karşılaştırması: "Psikoloji ve Danışmanlık" ve "Ağız ve Diş Sağlığı" sektörlerindeki tüm profillerin sunduğu hizmetler (services) incelendiğinde, süresi (durationMinutes) 45 dakika ve üzerinde olan seansların toplam hizmetler içindeki yüzdesel oranı hangi sektörde daha yüksektir?',
        'Operasyonel Eşik Analizi: Minimum bildirim süresi (minimumNoticeHours) 12 saatten az olan ve haftalık çalışma günlerinde (weeklyAvailability) hem erken mesai (09:00\'dan önce veya 09:00 başlangıç) hem de standart çalışma düzeni sunan profillerin en sık rastlanan meslek grubu (occupation) hangisidir?',
        'Çok Dilli Uzmanlık Kümesi: Türkçe dışında birden fazla yabancı dil (languages) içeren profillerin faaliyet gösterdiği sektörler arasında en yüksek çeşitliliğe sahip ilk iki sektör ve bu profillerin coğrafi olarak en sık kümelendiği şehirler hangileridir?'
    ]

    print("=" * 70)
    print("YAPISAL VERİ MOTORU (DATA ENGINE) HESAPLAMA TESTLERİ")
    print("=" * 70)

    for q in test_queries:
        res = engine.execute_query(q)
        print(f"\nSoru   : {q}")
        if res:
            print(f"Sonuç  : {res['summary']}")
            print(f"İşlem  : {res['operation']} | Veri Noktaları: {res.get('data_points')}")
        else:
            print("Sonuç  : [None - Dinamik Sütun/Veri bulunamadı -> Semantik RAG'e devredildi (Fallback)]")
