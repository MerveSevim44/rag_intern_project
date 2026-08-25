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
    from src.code_interpreter import code_interpreter_with_retry, build_correction_prompt
    from src.sandbox import safe_execute
except ImportError:
    from code_interpreter import code_interpreter_with_retry, build_correction_prompt
    from sandbox import safe_execute

def test_retry_simulation():
    df = pd.DataFrame({
        "employee_id": [1, 2, 3, 4],
        "department": ["IT", "HR", "IT", "Finance"],
        "salary_amount": [50000, 45000, 65000, 70000]
    })

    # Simüle edilmiş hatalı kod (KeyError: 'salary')
    bad_code = "result = df.groupby('department')['salary'].mean().to_dict()"
    res_bad = safe_execute(bad_code, df)
    print("1. Hatalı Kod Çalıştırma Çıktısı:", res_bad)
    assert "error" in res_bad
    assert "KeyError" in res_bad["error"]

    # Düzeltilmiş kod
    fixed_code = "result = df.groupby('department')['salary_amount'].mean().to_dict()"
    res_fixed = safe_execute(fixed_code, df)
    print("2. Düzeltilmiş Kod Çıktısı:", res_fixed)
    assert isinstance(res_fixed, dict)
    assert res_fixed["IT"] == 57500.0

    print("🎉 RETRY SİMÜLASYONU VE HATA BESLEME TESTİ BAŞARILI!")

if __name__ == "__main__":
    test_retry_simulation()
