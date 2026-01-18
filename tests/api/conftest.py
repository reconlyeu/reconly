"""API test configuration and fixtures.

Database fixtures are inherited from tests/conftest.py.
This file only contains API-specific fixtures (test client).

Note: Database availability check and skip logic is in tests/conftest.py
via pytest_collection_modifyitems hook.
"""
import os

# Override DATABASE_URL before importing the app to use test database
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql://reconly:reconly_dev@localhost:5432/reconly_test")
)

# Disable rate limiting during tests by setting a very high limit
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def client(test_connection, test_db):
    """Create a FastAPI test client that shares the database connection.

    The client's database sessions use the same connection as test_db,
    ensuring data created in tests is visible to API endpoints.
    """
    from reconly_api import dependencies
    from reconly_api.main import app

    # Store original values for cleanup
    original_engine = dependencies.engine
    original_session_local = dependencies.SessionLocal

    # Override get_db to use the shared test connection
    def override_get_db():
        Session = sessionmaker(bind=test_connection)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[dependencies.get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup: restore original values
    app.dependency_overrides.clear()
    dependencies.engine = original_engine
    dependencies.SessionLocal = original_session_local
