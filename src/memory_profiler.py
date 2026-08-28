"""
memory_profiler.py — RAG Pipeline Bellek Profiling Modülü

ÖLÇÜM FELSEFESİ (v2)
────────────────────
Bu modül üç bellek alanını BİRBİRİNDEN AYIRARAK ölçer. Karıştırmak,
"pipeline 11 GB tutuyor" gibi yanıltıcı teşhislere yol açar:

  1. Bu Python sürecinin RSS'i  → psutil.Process(os.getpid()).memory_info().rss
     Sadece bizim kodumuz: numpy matrisleri, BM25 indeksi, reranker (CPU).
  2. Yardımcı servis süreçleri  → ollama.exe / Foundry Local (AYRI PROCESS!)
     Embedding ve LLM modelleri BU süreçte değil, o süreçlerde durur.
     RSS'imize hiç yansımaz — ayrıca ölçülmeleri gerekir.
  3. Sistem geneli (OS+tarayıcı) → psutil.virtual_memory().used
     Pipeline'a AİT DEĞİLDİR. Sadece "makinede yer kaldı mı" sorusunu
     cevaplar; asla pipeline maliyeti olarak raporlanmaz.

Tüm raporlama, pipeline başlamadan önce alınan BASELINE'a göre DELTA
şeklindedir. Mutlak sayılar yalnızca bağlam olarak gösterilir.

Kullanım:
    profiler = MemoryProfiler()          # __init__ baseline'ı alır
    with profiler.measure("embedding", verify="ollama"):
        embedding = get_embedding(query)
    with profiler.measure("reranking"):
        results = rerank(query, docs)
    profiler.print_report()
"""

import gc
import os
import sys
import time
import functools
import subprocess
from contextlib import contextmanager

import psutil

# torch'u modül seviyesinde import ETMİYORUZ. embedder.py reranker'ı lazy
# import ettiği için, burada erken import etmek sırf profiling uğruna
# ~300-500 MB'lık bir torch (+ CUDA context) maliyetini pipeline'a ekler.
# Yalnızca başka bir modül zaten yüklediyse sys.modules üzerinden kullanırız.
_TORCH_CHECKED = False
_TORCH = None


def _torch():
    """torch'u yalnızca ZATEN yüklenmişse döner; kendisi import ETMEZ."""
    global _TORCH, _TORCH_CHECKED
    # Her çağrıda yeniden bakılır: reranker lazy import'tan sonra yüklenebilir.
    _TORCH = sys.modules.get("torch")
    _TORCH_CHECKED = True
    return _TORCH


def _cuda_ready():
    t = _torch()
    try:
        return bool(t and t.cuda.is_available())
    except Exception:
        return False


# ─── Yardımcı servis süreçleri (modeller BU süreçlerde durur) ────────────────
HELPER_PROCESS_HINTS = ("ollama", "foundry", "inference.service", "onnxruntime")


def _get_process_ram_mb():
    """SADECE bu Python sürecinin RSS'i (MB)."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def _get_helper_ram_mb():
    """
    Ollama / Foundry Local gibi yardımcı süreçlerin toplam RSS'i (MB).

    Embedding ve LLM modelleri bu süreçlerde yaşar; bizim RSS'imize
    yansımadıkları için ayrıca ölçülmeleri şart.
    """
    total = 0.0
    detail = {}
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (proc.info["name"] or "").lower()
            if any(h in name for h in HELPER_PROCESS_HINTS):
                mb = proc.info["memory_info"].rss / (1024 * 1024)
                total += mb
                detail[name] = detail.get(name, 0.0) + mb
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, TypeError):
            continue
    return total, detail


def _get_system_ram_mb():
    """Sistem geneli (MB). SADECE bağlam içindir — pipeline maliyeti DEĞİLDİR."""
    mem = psutil.virtual_memory()
    return mem.used / (1024 * 1024), mem.total / (1024 * 1024)


def _get_vram_mb():
    """
    Bu SÜRECİN CUDA üzerinde ayırdığı bellek (MB) — sistem GPU kullanımı değil.
    allocated = şu an canlı tensörler, reserved = allocator havuzu,
    peak = süreç ömrü boyunca tepe (max_memory_allocated).
    GPU yoksa (0, 0, 0) döner.
    """
    if not _cuda_ready():
        return 0.0, 0.0, 0.0
    t = _torch()
    return (
        t.cuda.memory_allocated() / (1024 * 1024),
        t.cuda.memory_reserved() / (1024 * 1024),
        t.cuda.max_memory_allocated() / (1024 * 1024),
    )


def snapshot():
    """
    Anlık bellek durumu.

    'process_ram_mb' bu sürecin RSS'idir — raporlamada ESAS alınan değer.
    'system_ram_used_mb' yalnızca bağlam bilgisidir, pipeline'a ait değildir.
    """
    sys_used, sys_total = _get_system_ram_mb()
    vram_alloc, vram_reserved, vram_peak = _get_vram_mb()
    helper_total, helper_detail = _get_helper_ram_mb()
    return {
        "process_ram_mb": round(_get_process_ram_mb(), 1),
        "helper_ram_mb": round(helper_total, 1),
        "helper_detail": {k: round(v, 1) for k, v in helper_detail.items()},
        "system_ram_used_mb": round(sys_used, 1),
        "system_ram_total_mb": round(sys_total, 1),
        "vram_allocated_mb": round(vram_alloc, 1),
        "vram_reserved_mb": round(vram_reserved, 1),
        "vram_peak_mb": round(vram_peak, 1),
        "timestamp": time.time(),
    }


def ollama_loaded_models():
    """
    `ollama ps` çıktısını parse eder — keep_alive="0" ayarının modeli
    gerçekten unload ettiğini doğrulamak için.

    Returns:
        list[str]: Bellekte yüklü model adları (boş liste = unload doğrulandı).
        None: Ollama yok / erişilemedi (bilinmiyor).
    """
    try:
        out = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=15
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if len(lines) <= 1:  # yalnızca başlık satırı → hiçbir model yüklü değil
        return []
    return [ln.split()[0] for ln in lines[1:]]


def foundry_loaded_models(base_url=None):
    """
    Foundry Local'de yüklü modelleri döner — TTL'nin gerçekten unload
    tetiklediğini doğrulamak için. Erişilemezse None (bilinmiyor).
    """
    import json
    import urllib.error
    import urllib.request

    if base_url is None:
        get_url = None
        for mod in ("src.llm_client", "llm_client"):
            try:
                m = __import__(mod, fromlist=["_discover_endpoint"])
            except ImportError:
                continue
            get_url = getattr(m, "_discover_endpoint", None)
            if get_url:
                break
        if not get_url:
            return None
        try:
            base_url = get_url()
        except Exception:
            return None
    if not base_url:
        return None
    try:
        with urllib.request.urlopen(f"{base_url}/openai/loadedmodels", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if isinstance(data, list):
        return [d if isinstance(d, str) else d.get("name", str(d)) for d in data]
    return None


class MemoryProfiler:
    """
    Pipeline adımlarının bellek kullanımını BASELINE'A GÖRE DELTA olarak ölçer.

    Baseline, hiçbir model yüklenmeden — profiler oluşturulduğu anda — alınır.
    Her adım "+X MB (baseline'a göre artış)" şeklinde raporlanır.
    """

    def __init__(self, take_baseline=True):
        self._steps = []  # [(name, snap_before, snap_after, duration_sec, notes)]
        self.baseline = None
        if take_baseline:
            self.reset_baseline()

    def reset_baseline(self):
        """
        Pipeline başlamadan HEMEN ÖNCE çağrılır: mevcut durumu sıfır noktası
        kabul eder. Bundan sonraki tüm rakamlar bu noktaya göre farktır.
        """
        gc.collect()
        if _cuda_ready():
            _torch().cuda.reset_peak_memory_stats()
        self.baseline = snapshot()
        print(
            f"[memory] BASELINE  | süreç RSS: {self.baseline['process_ram_mb']:.1f} MB"
            f" | yardımcı servisler: {self.baseline['helper_ram_mb']:.1f} MB"
            f" | (sistem geneli {self.baseline['system_ram_used_mb']:.0f} MB — "
            f"pipeline'a ait DEĞİL)"
        )
        return self.baseline

    @contextmanager
    def measure(self, step_name: str, verify=None):
        """
        Bellek ölçümü.

        Args:
            step_name: Adım adı.
            verify: "ollama" | "foundry" | None — adım bitiminde ilgili
                servisin modeli gerçekten unload ettiğini doğrular.
        """
        gc.collect()
        if _cuda_ready():
            _torch().cuda.synchronize()

        snap_before = snapshot()
        t0 = time.perf_counter()

        yield

        if _cuda_ready():
            _torch().cuda.synchronize()
        duration = time.perf_counter() - t0

        # Temizliğin GERÇEKTEN işe yarayıp yaramadığını görmek için ölçümü
        # gc'den ÖNCE ve SONRA alıyoruz. İkisi arasındaki fark kapanmıyorsa
        # referans hâlâ bir yerde tutuluyor demektir (cache dict / cycle).
        snap_after_raw = snapshot()
        gc.collect()
        snap_after = snapshot()

        notes = {"rss_before_gc_mb": snap_after_raw["process_ram_mb"]}
        if verify == "ollama":
            notes["ollama_loaded"] = ollama_loaded_models()
        elif verify == "foundry":
            notes["foundry_loaded"] = foundry_loaded_models()

        self._steps.append((step_name, snap_before, snap_after, duration, notes))

        base = self.baseline or snap_before
        ram_vs_base = snap_after["process_ram_mb"] - base["process_ram_mb"]
        helper_vs_base = snap_after["helper_ram_mb"] - base["helper_ram_mb"]
        vram_vs_base = snap_after["vram_allocated_mb"] - base["vram_allocated_mb"]
        print(
            f"[memory] {step_name:<20} | "
            f"süreç RSS: {ram_vs_base:+8.1f} MB | "
            f"servisler: {helper_vs_base:+8.1f} MB | "
            f"VRAM: {vram_vs_base:+7.1f} MB | "
            f"Süre: {duration:.2f}s   (baseline'a göre)"
        )
        if notes.get("ollama_loaded") is not None:
            loaded = notes["ollama_loaded"]
            print("[memory]   └ ollama ps: " + (
                "hiçbir model yüklü değil ✓ (unload doğrulandı)"
                if not loaded else f"HÂLÂ YÜKLÜ ✗ → {loaded}"))
        if notes.get("foundry_loaded") is not None:
            loaded = notes["foundry_loaded"]
            print("[memory]   └ Foundry: " + (
                "yüklü model yok ✓ (TTL unload doğrulandı)"
                if not loaded else f"HÂLÂ YÜKLÜ ✗ → {loaded}"))

    def print_report(self):
        """Adım bazlı, BASELINE'A GÖRE DELTA raporu."""
        if not self._steps:
            print("[memory] Henüz ölçüm yapılmadı.")
            return

        base = self.baseline or self._steps[0][1]

        print("\n" + "=" * 104)
        print("BELLEK PROFİLİ RAPORU — tüm değerler BASELINE'A GÖRE ARTIŞTIR")
        print("=" * 104)
        print(
            f"Baseline (model yüklenmeden önce): süreç RSS "
            f"{base['process_ram_mb']:.1f} MB, yardımcı servisler "
            f"{base['helper_ram_mb']:.1f} MB"
        )
        print("-" * 104)
        print(
            f"{'Adım':<20} | {'ΔSüreç RSS':>12} | {'ΔServisler':>12} | "
            f"{'ΔVRAM':>10} | {'ΔBu adım':>10} | {'Süre':>8}"
        )
        print("-" * 104)

        peak_ram_delta = 0.0
        peak_ram_step = ""
        peak_total_delta = 0.0
        peak_total_step = ""
        peak_vram_delta = 0.0
        peak_vram_step = ""

        for name, before, after, duration, notes in self._steps:
            ram_vs_base = after["process_ram_mb"] - base["process_ram_mb"]
            helper_vs_base = after["helper_ram_mb"] - base["helper_ram_mb"]
            vram_vs_base = after["vram_allocated_mb"] - base["vram_allocated_mb"]
            step_only = after["process_ram_mb"] - before["process_ram_mb"]
            total_vs_base = ram_vs_base + helper_vs_base

            print(
                f"{name:<20} | {ram_vs_base:>+11.1f}  | {helper_vs_base:>+11.1f}  | "
                f"{vram_vs_base:>+9.1f}  | {step_only:>+9.1f}  | {duration:>7.2f}s"
            )

            if ram_vs_base > peak_ram_delta:
                peak_ram_delta, peak_ram_step = ram_vs_base, name
            if total_vs_base > peak_total_delta:
                peak_total_delta, peak_total_step = total_vs_base, name
            if vram_vs_base > peak_vram_delta:
                peak_vram_delta, peak_vram_step = vram_vs_base, name

        print("-" * 104)
        print(f"Tepe süreç RSS artışı : {peak_ram_delta:+.1f} MB (adım: {peak_ram_step})")
        print(
            f"Tepe TOPLAM pipeline  : {peak_total_delta:+.1f} MB "
            f"(süreç + yardımcı servisler, adım: {peak_total_step})"
        )
        if _cuda_ready():
            peak_proc_vram = _get_vram_mb()[2]
            print(
                f"Tepe VRAM (bu süreç)  : {peak_vram_delta:+.1f} MB delta / "
                f"{peak_proc_vram:.1f} MB max_memory_allocated (adım: {peak_vram_step})"
            )

        # Temizlik doğrulaması
        for name, before, after, duration, notes in self._steps:
            raw = notes.get("rss_before_gc_mb")
            if raw is None:
                continue
            freed = raw - after["process_ram_mb"]
            if freed > 50:
                print(f"  [temizlik] {name}: gc.collect() {freed:.1f} MB serbest bıraktı.")
            elif after["process_ram_mb"] - before["process_ram_mb"] > 200:
                print(
                    f"  [not] {name}: RSS {after['process_ram_mb'] - before['process_ram_mb']:+.1f} MB "
                    f"kalıcı arttı ve gc bunu geri almadı. Adım ağır bir modülü İLK KEZ "
                    f"import ediyorsa (torch ~175 MB + sentence_transformers ~155 MB) bu "
                    f"NORMALDİR — modüller süreç ömrü boyunca yüklü kalır, sızıntı değildir. "
                    f"Ayırt etmek için aynı adımı arka arkaya çağırın: RSS her çağrıda "
                    f"artıyorsa referans tutuluyordur (cache dict / circular reference), "
                    f"sabitse tek seferlik import maliyetidir."
                )

        final = self._steps[-1][2]
        sys_pct = (final["system_ram_used_mb"] / final["system_ram_total_mb"] * 100
                   if final["system_ram_total_mb"] > 0 else 0)
        sys_baseline = (base["system_ram_used_mb"] - base["process_ram_mb"]
                        - base["helper_ram_mb"])
        print("-" * 104)
        print(
            f"BAĞLAM (pipeline'a ait DEĞİL): sistem geneli "
            f"{final['system_ram_used_mb']:.0f} / {final['system_ram_total_mb']:.0f} MB "
            f"(%{sys_pct:.1f}) — bunun ~{sys_baseline:.0f} MB'ı OS + diğer "
            f"uygulamaların baseline kullanımıdır."
        )
        if final["helper_detail"]:
            print("Yardımcı servis dağılımı: " + ", ".join(
                f"{k}={v:.0f} MB" for k, v in sorted(
                    final["helper_detail"].items(), key=lambda x: -x[1])))
        print("=" * 104 + "\n")

    def reset(self):
        """Ölçüm geçmişini temizler (baseline korunur)."""
        self._steps.clear()

    @property
    def steps(self):
        """Ölçüm adımlarını döner (test/debug için)."""
        return list(self._steps)


def profile_step(step_name: str):
    """
    Dekoratör: Fonksiyonun bellek kullanımını ölçer ve loglar.

    Çağrı ÖNCESİ durumu sıfır noktası kabul eder; delta olarak raporlar.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            gc.collect()
            snap_before = snapshot()
            t0 = time.perf_counter()

            result = func(*args, **kwargs)

            duration = time.perf_counter() - t0
            gc.collect()
            snap_after = snapshot()

            ram_delta = snap_after["process_ram_mb"] - snap_before["process_ram_mb"]
            helper_delta = snap_after["helper_ram_mb"] - snap_before["helper_ram_mb"]
            vram_delta = snap_after["vram_allocated_mb"] - snap_before["vram_allocated_mb"]
            print(
                f"[memory] {step_name:<20} | "
                f"süreç RSS: {ram_delta:+8.1f} MB | "
                f"servisler: {helper_delta:+8.1f} MB | "
                f"VRAM: {vram_delta:+7.1f} MB | "
                f"Süre: {duration:.2f}s   (çağrı öncesine göre)"
            )
            return result
        return wrapper
    return decorator
