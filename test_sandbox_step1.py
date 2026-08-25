import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

import pandas as pd
from sandbox import safe_execute

def test_sandbox():
    df = pd.DataFrame({
        "a": [10, 20, 30],
        "city": ["Istanbul", "Ankara", "Izmir"],
        "sector": ["Tech", "Health", "Tech"]
    })

    print("=== TEST 1: Basit Toplam ===")
    r1 = safe_execute("result = df['a'].sum()", df)
    print("Sonuç:", r1, "| Başarılı mı?", r1 == 60)
    assert r1 == 60

    print("\n=== TEST 2: Filtreleme & Value Counts ===")
    r2 = safe_execute("result = df[df['sector'] == 'Tech']['city'].tolist()", df)
    print("Sonuç:", r2, "| Başarılı mı?", r2 == ["Istanbul", "Izmir"])
    assert r2 == ["Istanbul", "Izmir"]

    print("\n=== TEST 3: Yasaklı import Engelleme ===")
    r3 = safe_execute("import os\nresult = os.getcwd()", df)
    print("Sonuç:", r3)
    assert isinstance(r3, dict) and "error" in r3 and "Güvenlik İhlali" in r3["error"]

    print("\n=== TEST 4: Yasaklı open Engelleme ===")
    r4 = safe_execute("result = open('rag.db', 'rb').read()", df)
    print("Sonuç:", r4)
    assert isinstance(r4, dict) and "error" in r4 and "Güvenlik İhlali" in r4["error"]

    print("\n=== TEST 5: Yasaklı eval / exec Engelleme ===")
    r5 = safe_execute("result = eval('1+1')", df)
    print("Sonuç:", r5)
    assert isinstance(r5, dict) and "error" in r5

    print("\n=== TEST 6: Hatalı Kod / KeyError Yakalama ===")
    r6 = safe_execute("result = df['olmayan_kolon'].mean()", df)
    print("Sonuç:", r6)
    assert isinstance(r6, dict) and "error" in r6 and "KeyError" in r6["error"]

    print("\n=== TEST 7: Zaman Aşımı (Timeout) ===")
    r7 = safe_execute("import time\ntime.sleep(10)", df, timeout_seconds=1)
    # import time is caught by security first, let's test pure while loop timeout
    r7_timeout = safe_execute("i = 0\nwhile i < 10**9:\n    i = (i + 1) % 1000\nresult = i", df, timeout_seconds=1)
    print("Sonuç:", r7_timeout)
    assert isinstance(r7_timeout, dict) and "error" in r7_timeout and "aşıldı" in r7_timeout["error"]

    print("\n🎉 SANDBOX İZOLE TESTLERİ BAŞARIYLA TAMAMLANDI!")

if __name__ == "__main__":
    test_sandbox()
