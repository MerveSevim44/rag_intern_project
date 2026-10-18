"""
Madde 29 regresyon testleri
(docs/implementation_plan_madde29_embedding_cihaz.md).

rag.db'deki 911 chunk'ın tamamının GPU ile üretildiği doğrulandığı için
(experiments/madde29_embedding_cihaz/), `embedder.get_embedding` ve
`get_embeddings` artık Ollama'ya `options={"num_gpu": EMBED_NUM_GPU}`
iletiyor; aksi halde Ollama çalışma anındaki VRAM durumuna göre CPU/GPU
arasında geçiş yapıp sorgu-doküman arasında sayısal kaymaya (cosine
~0.9982'ye kadar) yol açıyordu.

Servis gerekmez: `embedder.ollama` sahte bir modülle değiştirilir.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import embedder  # noqa: E402


class _FakeOllama:
    def __init__(self):
        self.calls = []

    def embed(self, model, input, keep_alive, options):
        self.calls.append({"model": model, "input": input,
                            "keep_alive": keep_alive, "options": options})
        n = 1 if isinstance(input, str) else len(input)

        class _Resp:
            embeddings = [[1.0, 0.0, 0.0]] * n
        return _Resp()


@pytest.fixture
def fake_ollama(monkeypatch):
    fake = _FakeOllama()
    monkeypatch.setattr(embedder, "ollama", fake)
    return fake


def test_get_embedding_varsayilan_num_gpu(fake_ollama):
    embedder.get_embedding("test")

    assert len(fake_ollama.calls) == 1
    assert fake_ollama.calls[0]["options"] == {"num_gpu": embedder.EMBED_NUM_GPU}
    assert embedder.EMBED_NUM_GPU == 99


def test_get_embedding_num_gpu_override(fake_ollama):
    embedder.get_embedding("test", num_gpu=0)

    assert fake_ollama.calls[0]["options"] == {"num_gpu": 0}


def test_get_embeddings_varsayilan_num_gpu(fake_ollama):
    embedder.get_embeddings(["test1", "test2"])

    assert len(fake_ollama.calls) == 1
    assert fake_ollama.calls[0]["options"] == {"num_gpu": embedder.EMBED_NUM_GPU}


def test_get_embeddings_num_gpu_override_tum_batchlere_geciyor(fake_ollama):
    embedder.get_embeddings(["t1", "t2", "t3"], batch_size=1, num_gpu=0)

    assert len(fake_ollama.calls) == 3
    assert all(c["options"] == {"num_gpu": 0} for c in fake_ollama.calls)
