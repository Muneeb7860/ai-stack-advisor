"""Shared skip gate for tests that exercise REAL embeddings.

app/retrieval.py embeds via the local Ollama daemon's /api/embed endpoint
(OllamaEmbeddingFunction). There is no offline fixture and no committed index, so with no
daemon reachable these tests fail on missing infrastructure rather than on retrieval
quality — the opposite of what they exist to measure.

Same idiom as test_architecture_contracts.py's requires_node: skip honestly rather than fail
misleadingly.

NOTE: CI (.github/workflows/ci.yml) runs without an Ollama daemon and therefore SKIPS every
test guarded by this marker — retrieval quality is not enforced there. Run the suite locally
with `ollama serve` + `ollama pull nomic-embed-text` before changing app/retrieval.py.
"""
import pytest


def _ollama_reachable() -> bool:
    import httpx

    from app.config import settings

    try:
        httpx.get(f"{settings.ollama_base_url}/api/version", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="local Ollama daemon not reachable — this test needs real embeddings (see tests/ollama_gate.py)",
)
