"""The database URL a managed host hands you is not the one SQLAlchemy accepts.

Render, Heroku and Railway all expose their managed Postgres on the legacy `postgres://`
scheme. SQLAlchemy dropped that alias in 2.x, so `create_engine()` raises
`Can't load plugin: sqlalchemy.dialects:postgres` — at import time, from db.py, before a single
request is served. The host surfaces that only as a failed health check on a container that
"won't start", which is a long way from the cause.

It also fails twice: the container CMD runs `alembic upgrade head` before uvicorn, and alembic
reads the same setting, so a fix applied in db.py alone would still fail the migration step
first. Hence the normalisation lives on Settings, where every consumer sees it.
"""
import pytest

from app.config import Settings


@pytest.mark.parametrize("supplied,expected", [
    # What Render's fromDatabase / Heroku's DATABASE_URL actually contain.
    ("postgres://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
    # Valid for SQLAlchemy, but leaves the DBAPI to discovery; this image ships psycopg2-binary.
    ("postgresql://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
    # Already explicit — must pass through untouched, not double-prefixed.
    ("postgresql+psycopg2://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
])
def test_managed_host_schemes_normalise_to_an_installed_driver(supplied, expected):
    assert Settings(database_url=supplied).database_url == expected


def test_a_non_postgres_url_is_left_alone():
    """SQLite is what the test suite itself runs on — normalisation must not touch it."""
    assert Settings(database_url="sqlite:///./test.db").database_url == "sqlite:///./test.db"


def test_credentials_containing_the_scheme_text_survive():
    """A password may legitimately contain 'postgres://'. Only the leading scheme is rewritten,
    so this checks the replacement is anchored rather than a global substitution."""
    url = "postgres://u:postgres://x@host:5432/db"
    assert Settings(database_url=url).database_url == "postgresql+psycopg2://u:postgres://x@host:5432/db"


def test_the_engine_actually_builds_from_a_render_style_url():
    """The assertions above compare strings; this one proves the normalised value is something
    SQLAlchemy will accept, which is the property that was actually broken."""
    from sqlalchemy import create_engine

    url = Settings(database_url="postgres://u:p@host:5432/db").database_url
    engine = create_engine(url)  # lazy — no connection attempted
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg2"


def test_the_value_read_from_the_environment_is_normalised(monkeypatch):
    """The deploy supplies this through the environment, not a constructor argument, so read it
    that way.

    Deliberately NOT `importlib.reload(app.config)`: config.py exposes a module-level `settings`
    singleton that every router captured with `from ..config import settings` at import time.
    Reloading swaps that object underneath them, and the damage lands in whichever test runs
    next — the first version of this file reloaded, passed in isolation, and broke
    test_refine.py::test_refine_ollama_provider_works_when_enabled several files later.
    Constructing a fresh Settings() exercises the same env-parsing path with no global effect.
    """
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert Settings().database_url == "postgresql+psycopg2://u:p@host:5432/db"
