from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config. Values load from environment / .env — see .env.example for the
    full list and the reasoning behind each one (especially the API-key note)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://advisor:advisor@localhost:5432/advisor"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    # --- Retrieval embeddings (app/retrieval.py) ---
    # Local-first per the project's own framing (see retrieval.py's module docstring): the
    # embedding model is served by the same local Ollama daemon already used for the
    # local-LLM-fallback path below, not a cloud embeddings API.
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Local-model fallback for /api/refine and /api/ask (see routers/refine.py, ask.py) ---
    # "anthropic" (default) keeps Claude as the primary/only provider, matching the locked
    # decision that the Anthropic API key comes from the request body — this setting only
    # controls whether an *additional*, opt-in, clearly-degraded local path is offered when
    # the caller has no Anthropic key. "ollama" opts a deployment into offering that path.
    llm_provider: str = "anthropic"
    ollama_model: str = "qwen2.5:7b"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
