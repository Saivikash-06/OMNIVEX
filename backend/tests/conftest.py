import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import Settings, settings
from backend.app.database.connection import Base, get_db
from backend.app.main import create_app


@pytest.fixture(scope="session")
def temp_dirs():
    """Create isolated temporary storage directories for test session."""
    temp_dir = tempfile.mkdtemp(prefix="omnivex_test_")
    p = Path(temp_dir)
    data_dir = p / "data"
    uploads_dir = p / "data" / "uploads"
    models_dir = p / "data" / "models"
    results_dir = p / "results"
    
    for d in [data_dir, uploads_dir, models_dir, results_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    yield {
        "root": p,
        "data": data_dir,
        "uploads": uploads_dir,
        "models": models_dir,
        "results": results_dir,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def test_db_engine(temp_dirs):
    """Create an isolated SQLite database file inside temp dir."""
    db_path = temp_dirs["root"] / "test_omnivex.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Provide a database session per test."""
    session = sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False, future=True)()
    yield session
    session.close()


@pytest.fixture
def test_app(temp_dirs, test_db_engine):
    """FastAPI test application with overridden settings and storage directories."""
    app = create_app()

    # Override settings for tests
    settings.DATA_DIR = temp_dirs["data"]
    settings.UPLOAD_DIR = temp_dirs["uploads"]
    settings.MODEL_DIR = temp_dirs["models"]
    settings.RESULTS_DIR = temp_dirs["results"]
    settings.OMNIVEX_API_KEY = None  # Default open for general tests

    # Dependency override for DB session
    def override_get_db() -> Generator[Session, None, None]:
        session = sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False, future=True)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app) -> Generator[TestClient, None, None]:
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
