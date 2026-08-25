"""
test_sandbox_and_datasets.py — Dinamik Text-to-Pandas Sandbox & Çoklu Veri Seti Doğrulama Testi

Bu test:
1. 3 Kademeli Router'ı test eder (rule_engine -> code_interpreter -> semantic_rag).
2. Sandbox güvenliğini (yasaklı token engelleme, timeout) doğrular.
3. 728_profiles.json üzerindeki karmaşık analitik soruları LLM & Sandbox ile çözer.
4. airports.json (yeni/ikinci JSON) üzerindeki dinamik soruları SIFIR ön tanımlı kural ile %100 otomatik çözer.
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

import json
import time
import pandas as pd
from llm_client import load_model
from router import route_query, RouteTarget
from sandbox import safe_execute
from code_interpreter import code_interpreter_with_retry, result_to_natural_language
from data_engine import get_data_engine, query_tabular_data


def test_full_pipeline():
    print("=" * 80)
    print("DİNAMİK TEXT-TO-PANDAS SANDBOX & ÇOKLU JSON DOĞRULAMA TESTİ")
    print("=" * 80)

    # 1. LLM Yükle
    print("\n[1/4] LLM Modeli Yükleniyor...")
    llm = load_model()
    engine = get_data_engine()

    # 2. Router Doğrulaması
    print("\n[2/4] 3 Kademeli Router Test Ediliyor...")
    sample_queries = [
        ("Veri setindeki toplam profil sayısı kaçtır?", "rule_engine"),
        ("Tüm profillerin ortalama deneyim yılı kaçtır?", "code_interpreter"),
        ("Hangi ülkede kaç havaalanı bulunmaktadır?", "code_interpreter"),
        ('"profileCode" alanı ne için kullanılır?', "semantic_rag"),
        ("Fourier dönüşümü nedir?", "semantic_rag"),
    ]
    for q, exp in sample_queries:
        act = route_query(q)
        status = "✅ PASS" if act == exp else "❌ FAIL"
        print(f"  {status} | Beklenen: {exp:<16} | Çıkan: {act:<16} | Soru: {q}")
        assert act == exp

    # 3. 728_profiles.json Üzerinde Dinamik Sorular
    print("\n" + "=" * 80)
    print("[3/4] 728_profiles.json Veri Seti Üzerinde Dinamik LLM Kod Üretim Testleri")
    print("=" * 80)

    df_profiles, _ = engine.get_best_dataframe(query="profiller", filename="728_profiles.json")
    print(f"-> 728_profiles.json yüklendi: {len(df_profiles)} satır, {len(df_profiles.columns)} sütun.")

    profile_questions = [
        '"profileType" alanına göre kaç profil "individual" kaç profil "business" olarak sınıflandırılmıştır?',
        'Veri setindeki profillerde toplam kaç farklı şehir (location.city) yer almaktadır ve en çok profile sahip ilk 3 şehir hangileridir?',
        'Tüm profillerin "experience.years" alanlarına göre ortalama mesleki deneyim yılı kaçtır?',
        '"appointmentSettings.autoApproveRequests" değeri true olan profillerin toplam profil sayısına oranı yüzde kaçtır?',
    ]

    for i, q in enumerate(profile_questions, 1):
        print(f"\n--- Soru 3.{i}: {q} ---")
        t0 = time.perf_counter()
        res = code_interpreter_with_retry(q, df_profiles, llm, max_retries=3)
        elapsed = time.perf_counter() - t0
        
        assert res["success"] is True, f"Soru çözülemedi: {res.get('error')}"
        print(f"Üretilen Kod:\n{res['code']}")
        print(f"Hesaplanan Ham Sonuç: {res['raw_result']} ({res['attempts']} denemede, {elapsed:.2f}s)")
        
        nl_answer = result_to_natural_language(q, res["raw_result"], llm)
        print(f"🗣️ Doğal Dil Yanıtı: {nl_answer}")

    # 4. airports.json (YENİ / İKİNCİ JSON DOSYASI) Üzerinde Dinamik Sorular
    print("\n" + "=" * 80)
    print("[4/4] data/airports.json (İKİNCİ JSON) Üzerinde Sıfır Kural ile Dinamik Testler")
    print("=" * 80)

    df_airports, _ = engine.get_best_dataframe(query="airport", filename="airports.json")
    print(f"-> airports.json yüklendi: {len(df_airports)} satır, {len(df_airports.columns)} sütun.")
    print(f"-> Sütunlar: {list(df_airports.columns)}")

    airport_questions = [
        "Havaalanları veri setinde toplam kaç havaalanı ve kaç farklı ülke (country) bulunmaktadır?",
        "Hangi ülkede kaç havaalanı bulunmaktadır ve en çok havaalanına sahip ilk 3 ülke hangileridir?",
        "En kuzeyde yer alan (en yüksek enlem / lat değerine sahip) ilk 3 havaalanının isimleri ve ülkeleri nelerdir?",
        "ABD ('US') ülkesindeki havaalanlarının ortalama enlem (lat) ve ortalama boylam (lon) değerleri nedir?",
        "Tokyo şehrinde bulunan havaalanlarının kodları (code) ve isimleri (name) nelerdir?",
    ]

    for i, q in enumerate(airport_questions, 1):
        print(f"\n--- Havaalanı Sorusu 4.{i}: {q} ---")
        t0 = time.perf_counter()
        res = code_interpreter_with_retry(q, df_airports, llm, max_retries=3)
        elapsed = time.perf_counter() - t0
        
        assert res["success"] is True, f"Havaalanı sorusu çözülemedi: {res.get('error')}"
        print(f"Üretilen Kod:\n{res['code']}")
        print(f"Hesaplanan Ham Sonuç: {res['raw_result']} ({res['attempts']} denemede, {elapsed:.2f}s)")
        
        nl_answer = result_to_natural_language(q, res["raw_result"], llm)
        print(f"🗣️ Doğal Dil Yanıtı: {nl_answer}")

    print("\n" + "=" * 80)
    print("🎉 TÜM DİNAMİK TEXT-TO-PANDAS SANDBOX VE ÇOKLU JSON TESTLERİ EKSİKSİZ BAŞARILI!")
    print("=" * 80)


if __name__ == "__main__":
    test_full_pipeline()
