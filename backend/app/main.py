import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import ask, disagreements, harness_feedback, recommend, refine, share

# Without this, Python's logging module has no handler attached and every logger.info() call
# in this codebase — including llm_providers.py's native-vs-fallback tool-call-path logging,
# which exists specifically as the eval signal for measuring how often the Ollama fallback
# path fires in production (see its SECURITY comment) — silently goes nowhere. Found via a
# real live test: a request that should have logged its extraction path produced zero log
# output in `docker compose logs`. INFO level, stdout, so Docker/any log aggregator captures it.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="AI Stack Advisor — v2 Backend",
    description=(
        "Optional backend for v2 features (LLM refinement, share links, MCP tool, structured recommendations). "
        "v1 (index.html) remains fully functional with zero backend calls — see PRD NFR-5. "
        "This backend must never become a hard dependency for the core v1 experience."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # no auth/cookies in this design — see share.py docstring
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(share.router)
app.include_router(refine.router)
app.include_router(ask.router)
app.include_router(recommend.router)
app.include_router(disagreements.router)
app.include_router(harness_feedback.router)


@app.get("/health")
def health():
    return {"status": "ok"}
