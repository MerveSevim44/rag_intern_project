"""
sandbox.py — Güvenli Pandas Kod Çalıştırma Ortamı (Sandbox)

LLM tarafından üretilen Python/Pandas kodlarını kısıtlı ve güvenli bir ortamda çalıştırır.
Özellikler:
1. AST (Soyut Sözdizim Ağacı) tabanlı derin güvenlik analizi (Import, dosya, ağ, eval engeli).
2. Sütun isimleriyle çakışmayan akıllı güvenlik denetimi (Örn: 'autoApproveRequests' sütunu güvenle çalışır).
3. Kısıtlı Builtin namespace (__builtins__ sınırlandırması).
4. DataFrame izolasyonu (Orijinal verinin bozulmaması için df.copy() kullanımı).
5. Cross-Platform Non-Blocking Timeout (Windows & Linux uyumlu daemon thread zaman aşımı koruması).
"""

import ast
import math
import re
import threading
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np


class TimeoutException(Exception):
    """Kod çalışma süresi aşıldığında fırlatılır."""
    pass


# İzin verilen güvenli yerleşik fonksiyonlar
SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "sum": sum,
    "min": min,
    "max": max,
    "round": round,
    "int": int,
    "float": float,
    "str": str,
    "dict": dict,
    "list": list,
    "set": set,
    "tuple": tuple,
    "bool": bool,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "abs": abs,
    "all": all,
    "any": any,
    "isinstance": isinstance,
    # Çok adımlı/matematiksel kodun ihtiyaç duyduğu, yan etkisiz yerleşikler.
    # Bunlar olmadan model map/filter/reversed kullanan tamamen masum kod
    # ürettiğinde NameError alıp retry döngüsünü boşa harcıyordu.
    "map": map,
    "filter": filter,
    "reversed": reversed,
    "divmod": divmod,
    "pow": pow,
    "format": format,
    "repr": repr,
    "type": type,
    "print": lambda *args, **kwargs: None,  # print çağrılarını yut
    "None": None,
    "True": True,
    "False": False,
}

# Yasaklı modül ve fonksiyon adları (AST düğümlerinde kontrol edilir)
FORBIDDEN_CALLS = {
    "open", "exec", "eval", "compile", "globals", "locals",
    "getattr", "setattr", "delattr", "breakpoint", "input",
    "memoryview", "exit", "quit", "__import__"
}

FORBIDDEN_NAMES = {
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib", "pty", "posix"
}



# ─────────────────────────────────────────────────────────────────────────────
# STANDART YARDIMCI FONKSIYON KUTUPHANESI (dataset-agnostik)
#
# Neden gerekli: prompt'a "su formulu aynen tanimla ve kullan" demek kucuk
# modellerde guvenilir degil — model formulu CAGIRIYOR ama TANIMLAMAYI atliyor
# ve NameError aliyor. Formulu ortamin kendisine koymak bu sinifi hatalari
# tamamen ortadan kaldirir: dogru formul her zaman tek bir yerde tanimlidir,
# model onu yeniden turetmez, sadece cagirir.
#
# Buraya eklenen her sey saf, yan etkisiz ve veri setinden bagimsiz olmalidir.
# ─────────────────────────────────────────────────────────────────────────────

EARTH_RADIUS_KM = 6371.0


def haversine(lat1, lon1, lat2, lon2, radius=EARTH_RADIUS_KM):
    """
    Iki koordinat arasindaki buyuk daire (great-circle) mesafesini km cinsinden
    doner. Skaler ve pandas Series/numpy dizisi girdileriyle vektorel calisir.
    """
    p1 = np.radians(np.asarray(lat1, dtype=float))
    p2 = np.radians(np.asarray(lat2, dtype=float))
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2.0) ** 2
    dist = 2.0 * radius * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    # Series girdisinde Series don ki .assign / kolon atamasi dogal calissin.
    if isinstance(lat2, pd.Series):
        return pd.Series(dist, index=lat2.index)
    if isinstance(lat1, pd.Series):
        return pd.Series(dist, index=lat1.index)
    return float(dist) if np.ndim(dist) == 0 else dist


def percent_change(old, new):
    """Yuzde degisim: (new - old) / old * 100. old = 0 ise NaN doner."""
    old_arr = np.asarray(old, dtype=float)
    new_arr = np.asarray(new, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(old_arr == 0, np.nan, (new_arr - old_arr) / old_arr * 100.0)
    return float(out) if np.ndim(out) == 0 else out


# Sandbox namespace'ine hazir olarak enjekte edilen isimler.
SAFE_HELPERS = {
    "haversine": haversine,
    "percent_change": percent_change,
    "EARTH_RADIUS_KM": EARTH_RADIUS_KM,
}


def clean_python_code(code_str: str) -> str:
    """LLM çıktısındaki markdown kod bloklarını (```python ... ```) ve çevreleyen metinleri temizler."""
    if not code_str:
        return ""
    
    # 1. Regex ile metin içindeki ```python ... ``` veya ``` ... ``` bloğunu çıkar
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", code_str, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. Eğer kapanış ``` yoksa ama ``` ile başlıyorsa satır satır temizle
    code = code_str.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code



def check_code_safety(code: str) -> Optional[str]:
    """
    AST (Abstract Syntax Tree) üzerinden kodu güvenliğe karşı denetler.
    Güvensiz bir yapı veya token tespit edilirse hata mesajı döner; güvenliyse None döner.
    """
    if not code or not code.strip():
        return "Boş kod çalıştırılamaz."

    # 1. AST Parsing
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError (Sözdizimi Hatası): {e.msg} (Satır {e.lineno})"

    # 2. AST Düğümlerini Gezerek Güvenlik İhlallerini Yakala
    for node in ast.walk(tree):
        # Import ifadeleri kesinlikle yasak
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "Güvenlik İhlali: Kod içinde 'import' ifadesi kullanılamaz."

        # Yasaklı fonksiyon çağrıları (open, eval, exec vb.)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return f"Güvenlik İhlali: Yasaklı fonksiyon çağrısı tespit edildi: '{node.func.id}()'"

        # Yasaklı modül/değişken isimleri (os, sys, subprocess vb.)
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return f"Güvenlik İhlali: Yasaklı modül/kütüphane referansı tespit edildi: '{node.id}'"

        # Dunder (__class__, __bases__, __subclasses__ vb.) erişimleri yasak
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"Güvenlik İhlali: Dunder ('__{node.attr}__') öznitelik erişimi yasaktır."

    return None


def _execute_in_sandbox(code: str, df: pd.DataFrame) -> Any:
    """
    Kısıtlı ve TEK bir namespace içinde kodu çalıştırır, 'result' değişkenini döner.

    NEDEN TEK NAMESPACE: Daha önce exec(code, safe_globals, safe_locals) şeklinde
    ayrı globals/locals sözlükleri veriliyordu. Python'da bir fonksiyon/lambda/
    comprehension gövdesi, kendisini çevreleyen exec'in LOCALS sözlüğünü GÖREMEZ;
    yalnızca globals'a bakar. Bu yüzden model şu tamamen doğru kodu ürettiğinde:

        def haversine(lat1, lon1, lat2, lon2):
            return 2 * 6371 * np.arcsin(...)      # -> NameError: 'np'

        distances = df.apply(lambda r: f(r, result), axis=1)  # -> NameError: 'result'

    sandbox "np/df/result tanımlı değil" hatası veriyordu. Yani hata modelin
    değil ortamın hatasıydı; retry döngüsü de düzeltilemez bir hatayı düzeltmeye
    çalışıp 3 denemeyi harcıyordu. Yardımcı fonksiyon tanımlamak çok adımlı
    (haversine, mesafe matrisi, özel skor) soruların DOĞAL çözüm biçimi olduğu
    için bu, veri setinden bağımsız yapısal bir kısıttı.
    """
    namespace: Dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "math": math,
        "result": None,
    }
    # Standart formul kutuphanesi (haversine vb.) hazir tanimli gelir; boylece
    # model dogru formulu yeniden yazmak zorunda kalmaz.
    namespace.update(SAFE_HELPERS)

    # Tek sözlük verilince exec bunu hem globals hem locals olarak kullanır;
    # böylece iç kapsamlar (fonksiyon/lambda) tüm isimleri görür.
    exec(code, namespace)

    if namespace.get("result") is None:
        raise ValueError("Kod çalıştırıldı ancak 'result' değişkenine bir değer atanmadı. Lütfen sonucu 'result = ...' şeklinde atayın.")

    return namespace.get("result")


def safe_execute(code: str, df: pd.DataFrame, timeout_seconds: int = 5) -> Union[Any, Dict[str, str]]:
    """
    Verilen pandas kodunu güvenli sandbox içerisinde çalıştırır.
    
    Args:
        code: Çalıştırılacak Python/Pandas kodu string'i.
        df: Üzerinde çalışılacak DataFrame.
        timeout_seconds: Maksimum izin verilen çalışma süresi (saniye).
        
    Returns:
        Başarılıysa hesaplanan 'result' nesnesi (Scalar, Series, DataFrame, Dict, List vb.).
        Hata durumunda {'error': 'Hata açıklaması'} sözlüğü döner.
    """
    cleaned_code = clean_python_code(code)
    
    # 1. AST Tabanlı Derin Güvenlik Kontrolü
    safety_error = check_code_safety(cleaned_code)
    if safety_error:
        return {"error": safety_error}
    
    # 2. Daemon Thread ile Non-Blocking Timeout Kontrolü
    result_box = {"result": None, "error": None}
    
    def target():
        try:
            result_box["result"] = _execute_in_sandbox(cleaned_code, df)
        except Exception as e:
            result_box["error"] = f"{type(e).__name__}: {str(e)}"

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return {"error": f"Kod çalışma süresi aşıldı ({timeout_seconds} saniye limit)"}
    
    if result_box["error"] is not None:
        return {"error": result_box["error"]}
    
    return result_box["result"]
