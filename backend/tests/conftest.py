"""Universal test configuration for ai-stack-advisor backend.

Provides a zero-dependency in-memory SQLite database fallback when a live Postgres instance
is not reachable at DATABASE_URL, allowing unit and integration tests to run cleanly in any
environment (CI, local dev, offline) without requiring `docker compose up -d db`.
"""
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Enable PostgreSQL JSONB compilation on SQLite
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(type_, **kw)

# 2. Patch PG_UUID bind processor to safely accept string UUIDs on SQLite
orig_bind_processor = PG_UUID.bind_processor

def safe_bind_processor(self, dialect):
    proc = orig_bind_processor(self, dialect)
    if proc is None:
        return None
    def safe_proc(value):
        if value is not None and isinstance(value, str):
            try:
                value = uuid.UUID(value)
            except ValueError:
                pass
        return proc(value)
    return safe_proc

PG_UUID.bind_processor = safe_bind_processor

# 3. Create global SQLite test engine with StaticPool
test_engine = sa.create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

from app.db import Base, get_db
import app.db as app_db
import app.mcp.server as mcp_server_module
from app.main import app

# Patch db engine and SessionLocal globally at module level
app_db.engine = test_engine
app_db.SessionLocal.configure(bind=test_engine)
mcp_server_module.engine = test_engine
mcp_server_module.SessionLocal.configure(bind=test_engine)

@pytest.fixture(autouse=True)
def setup_test_db():
    """Creates all tables before each test and drops them after."""
    Base.metadata.create_all(test_engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
