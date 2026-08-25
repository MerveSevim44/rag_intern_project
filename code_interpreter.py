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
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np

from sandbox import safe_execute, clean_python_code


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

    schema_info = f"""Mevcut DataFrame (df) Bilgisi:
- Toplam Satır Sayısı: {len(df)}
- Tüm Sütun İsimleri (Birebir kullan): {list(df.columns)}
- Sütunlar ve Veri Tipleri: {dtypes_dict}
- İlk 2 Satır Örnek Kayıt: {sample_json}"""

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

Soru: {question}

Kod:"""


def build_correction_prompt(question: str, df: pd.DataFrame, previous_code: str, error_message: str) -> str:
    """
    Hata durumunda LLM'e önceki hatayı ve kodu bildirerek düzeltme isteyen prompt.
    """
    base_prompt = build_code_gen_prompt(question, df)
    return f"""Önceki denemede üretilen kod HATA VERDİ:
Hata Mesajı: {error_message}

Hatalı Kod:
{previous_code}

Lütfen yukarıdaki hatayı analiz et ve hatayı gidererek sadece düzeltilmiş çalışan Python kodunu yaz.
Sonucu mutlaka 'result' değişkenine ata.

{base_prompt}"""


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
    verbose: bool = True
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
    prompt = build_code_gen_prompt(question, df)
    last_code = ""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        if verbose:
            print(f"[CodeInterpreter] Deneme {attempt}/{max_retries}...")

        # 1. LLM'den kod üret
        raw_code = call_llm_text(llm, prompt)
        code = clean_python_code(raw_code)
        last_code = code

        if verbose:
            print(f"[CodeInterpreter] Üretilen Kod:\n{code}")

        # 2. Güvenli Sandbox içinde çalıştır
        exec_result = safe_execute(code, df, timeout_seconds=timeout_seconds)

        # 3. Sonuç Kontrolü
        if isinstance(exec_result, dict) and "error" in exec_result:
            last_error = exec_result["error"]
            if verbose:
                print(f"[CodeInterpreter] Hata alındı ({attempt}. deneme): {last_error}")
            
            # Hatayı LLM'e geri besleyerek yeni prompt oluştur
            prompt = build_correction_prompt(question, df, code, last_error)
            continue
        else:
            # Başarılı çalıştırma!
            if verbose:
                print(f"[CodeInterpreter] Başarılı! Çıktı: {exec_result}")
            return {
                "success": True,
                "raw_result": exec_result,
                "code": code,
                "attempts": attempt,
                "error": None
            }

    # Tüm denemeler tükendi
    if verbose:
        print(f"[CodeInterpreter] {max_retries} deneme başarısız oldu. Son hata: {last_error}")
    return {
        "success": False,
        "raw_result": None,
        "code": last_code,
        "attempts": max_retries,
        "error": f"{max_retries} denemede çözülemedi: {last_error}"
    }


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
ÖNEMLİ KURAL: Sayıları, oranları, sıralamaları ve isimleri asla değiştirme veya uydurma, tam olarak hesaplama sonucunda ne varsa onu aktar.

Cevap:"""

    try:
        natural_text = call_llm_text(llm, prompt)
        return natural_text.strip()
    except Exception as e:
        return f"Hesaplama Sonucu: {formatted_result}"
