from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import ask, refine, share

app = FastAPI(
    title="AI Stack Advisor — v2 Backend",
    description=(
        "Optional backend for v2 features (LLM refinement, share links, MCP tool). "
        "v1 (index.html) remains fully functional with zero backend calls — see PRD NFR-5. "
        "This backend must never become a hard dependency for the core v1 experience."
    ),
    version="0.1.0",
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


@app.get("/health")
def health():
    return {"status": "ok"}
