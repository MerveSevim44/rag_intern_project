import sys
from pathlib import Path

# Add src and root to sys.path for direct script runs
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
for _p in [str(_src), str(_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

import pandas as pd
try:
    from src.llm_client import load_model
    from src.code_interpreter import code_interpreter_with_retry, result_to_natural_language
except ImportError:
    from llm_client import load_model
    from code_interpreter import code_interpreter_with_retry, result_to_natural_language

def test_code_interpreter():
    print("=== LLM YÜKLENİYOR ===")
    llm = load_model()
    
    # Test DataFrame
    df = pd.DataFrame({
        "name": ["Ali", "Ayşe", "Mehmet", "Zeynep", "Can"],
        "age": [25, 30, 35, 40, 28],
        "city": ["Istanbul", "Ankara", "Izmir", "Istanbul", "Ankara"],
        "salary": [45000, 60000, 75000, 85000, 50000]
    })
    
    print("\n--- TEST 1: Basit Soru (Ortalama Maaş) ---")
    q1 = "Tüm çalışanların ortalama maaşı kaçtır?"
    res1 = code_interpreter_with_retry(q1, df, llm, max_retries=3)
    print("Execution Result:", res1)
    assert res1["success"] is True
    nl1 = result_to_natural_language(q1, res1["raw_result"], llm)
    print("Doğal Dil Yanıtı:", nl1)

    print("\n--- TEST 2: Koşullu Filtreleme ve Gruplama (Istanbul'dakilerin Yaş Ortalaması) ---")
    q2 = "Istanbul şehrinde yaşayanların yaş ortalaması nedir ve kaç kişidir?"
    res2 = code_interpreter_with_retry(q2, df, llm, max_retries=3)
    print("Execution Result:", res2)
    assert res2["success"] is True
    nl2 = result_to_natural_language(q2, res2["raw_result"], llm)
    print("Doğal Dil Yanıtı:", nl2)

    print("\n🎉 CODE INTERPRETER & NATURAL LANGUAGE TESTLERİ BAŞARIYLA TAMAMLANDI!")

if __name__ == "__main__":
    test_code_interpreter()
