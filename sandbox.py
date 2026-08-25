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
    """Kısıtlı namespace içinde kodu çalıştırır ve 'result' değişkenini döner."""
    safe_globals = {"__builtins__": SAFE_BUILTINS}
    safe_locals = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "result": None,
    }
    
    exec(code, safe_globals, safe_locals)
    
    if "result" not in safe_locals or safe_locals["result"] is None:
        raise ValueError("Kod çalıştırıldı ancak 'result' değişkenine bir değer atanmadı. Lütfen sonucu 'result = ...' şeklinde atayın.")
        
    return safe_locals.get("result")


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
