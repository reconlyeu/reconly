"""Tests for Connection API routes.

Tests /api/v1/connections/ endpoints for CRUD operations and connection testing.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from reconly_core.database.models import Connection, Source


@pytest.fixture(autouse=True)
def set_secret_key(monkeypatch):
    """Set SECRET_KEY for all tests in this module."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-connections-api-tests-minimum-32-chars")


@pytest.fixture
def sample_connection(test_db) -> Connection:
    """Create a sample connection for testing."""
    connection = Connection(
        name="Test Connection",
        type="email_imap",
        provider="generic",
        config_encrypted="fake_encrypted_config",  # Will be properly encrypted in real tests
        created_at=datetime.utcnow(),
    )
    test_db.add(connection)
    test_db.commit()
    test_db.refresh(connection)
    return connection


@pytest.mark.api
class TestListConnections:
    """Test GET /api/v1/connections endpoint."""

    def test_list_connections_empty(self, client):
        """Test listing connections when none exist."""
        response = client.get("/api/v1/connections")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_connections(self, client, test_db):
        """Test listing connections."""
        # Create connections using the service (for proper encryption)
        from reconly_core.services.connection_service import create_connection

        connection1 = create_connection(
            db=test_db,
            name="Gmail Connection",
            connection_type="email_imap",
            config={"host": "imap.gmail.com", "port": 993, "username": "test@gmail.com", "password": "pass123"},
            provider="gmail",
        )
        connection2 = create_connection(
            db=test_db,
            name="API Connection",
            connection_type="api_key",
            config={"api_key": "sk-test123"},
        )
        test_db.commit()

        response = client.get("/api/v1/connections")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Verify response structure
        item = data["items"][0]
        assert "id" in item
        assert "name" in item
        assert "type" in item
        assert "provider" in item
        assert "has_password" in item
        assert "source_count" in item
        assert "created_at" in item

    def test_list_connections_filter_by_type(self, client, test_db):
        """Test filtering connections by type."""
        from reconly_core.services.connection_service import create_connection

        # Create connections of different types
        create_connection(
            db=test_db,
            name="IMAP Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        create_connection(
            db=test_db,
            name="API Connection",
            connection_type="api_key",
            config={"api_key": "key123"},
        )
        test_db.commit()

        # Filter by email_imap
        response = client.get("/api/v1/connections?type=email_imap")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "email_imap"

        # Filter by api_key
        response = client.get("/api/v1/connections?type=api_key")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "api_key"

    def test_list_connections_includes_source_count(self, client, test_db):
        """Test that connection list includes source count."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        test_db.commit()

        # Create sources using the connection
        source1 = Source(
            name="Source 1",
            type="imap",
            url="imap://test1",
            connection_id=connection.id,
            enabled=True,
        )
        source2 = Source(
            name="Source 2",
            type="imap",
            url="imap://test2",
            connection_id=connection.id,
            enabled=True,
        )
        test_db.add_all([source1, source2])
        test_db.commit()

        response = client.get("/api/v1/connections")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["source_count"] == 2

    def test_list_connections_excludes_encrypted_config(self, client, test_db):
        """Test that connection list excludes encrypted config from response."""
        from reconly_core.services.connection_service import create_connection

        create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "secret123"},
        )
        test_db.commit()

        response = client.get("/api/v1/connections")
        assert response.status_code == 200

        data = response.json()
        item = data["items"][0]

        # Verify password fields are not in response
        assert "config" not in item
        assert "config_encrypted" not in item
        assert "password" not in item
        # Should have has_password flag instead
        assert item["has_password"] is True


@pytest.mark.api
class TestCreateConnection:
    """Test POST /api/v1/connections endpoint."""

    def test_create_connection_email_imap(self, client):
        """Test creating an email IMAP connection."""
        connection_data = {
            "name": "My Gmail",
            "type": "email_imap",
            "provider": "gmail",
            "config": {
                "host": "imap.gmail.com",
                "port": 993,
                "username": "test@gmail.com",
                "password": "app_password",
                "use_ssl": True,
            },
        }

        response = client.post("/api/v1/connections", json=connection_data)
        assert response.status_code == 201

        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "My Gmail"
        assert data["type"] == "email_imap"
        assert data["provider"] == "gmail"
        assert data["has_password"] is True
        assert data["source_count"] == 0

    def test_create_connection_api_key(self, client):
        """Test creating an API key connection."""
        connection_data = {
            "name": "OpenAI API",
            "type": "api_key",
            "config": {
                "api_key": "sk-test123456",
                "endpoint": "https://api.openai.com/v1",
            },
        }

        response = client.post("/api/v1/connections", json=connection_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "OpenAI API"
        assert data["type"] == "api_key"
        assert data["provider"] is None

    def test_create_connection_http_basic(self, client):
        """Test creating an HTTP Basic Auth connection."""
        connection_data = {
            "name": "Basic Auth API",
            "type": "http_basic",
            "config": {
                "username": "api_user",
                "password": "api_password",
            },
        }

        response = client.post("/api/v1/connections", json=connection_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Basic Auth API"
        assert data["type"] == "http_basic"

    def test_create_connection_validation_error(self, client):
        """Test creating connection with invalid data."""
        # Missing required fields
        response = client.post("/api/v1/connections", json={})
        assert response.status_code == 422

        # Invalid type
        response = client.post(
            "/api/v1/connections",
            json={
                "name": "Test",
                "type": "invalid_type",
                "config": {},
            },
        )
        assert response.status_code == 422

    def test_create_connection_without_secret_key(self, client, monkeypatch):
        """Test that connection creation fails gracefully without SECRET_KEY."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        connection_data = {
            "name": "Test Connection",
            "type": "email_imap",
            "config": {
                "host": "imap.test.com",
                "username": "test",
                "password": "pass",
            },
        }

        response = client.post("/api/v1/connections", json=connection_data)
        assert response.status_code == 500
        assert "Failed to encrypt credentials" in response.text
        assert "SECRET_KEY" in response.text


@pytest.mark.api
class TestGetConnection:
    """Test GET /api/v1/connections/{id} endpoint."""

    def test_get_connection_by_id(self, client, test_db):
        """Test retrieving a specific connection."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
            provider="generic",
        )
        test_db.commit()

        response = client.get(f"/api/v1/connections/{connection.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == connection.id
        assert data["name"] == "Test Connection"
        assert data["type"] == "email_imap"
        assert data["provider"] == "generic"

    def test_get_connection_not_found(self, client):
        """Test retrieving a non-existent connection."""
        response = client.get("/api/v1/connections/99999")
        assert response.status_code == 404
        assert "Connection not found" in response.text

    def test_get_connection_excludes_credentials(self, client, test_db):
        """Test that GET connection excludes credentials from response."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={
                "host": "imap.test.com",
                "username": "test@example.com",
                "password": "secret123",
            },
        )
        test_db.commit()

        response = client.get(f"/api/v1/connections/{connection.id}")
        assert response.status_code == 200

        data = response.json()
        # Should not contain config or encrypted fields
        assert "config" not in data
        assert "config_encrypted" not in data
        assert "password" not in data


@pytest.mark.api
class TestUpdateConnection:
    """Test PATCH /api/v1/connections/{id} endpoint."""

    def test_update_connection_name(self, client, test_db):
        """Test updating connection name."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Original Name",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        test_db.commit()

        update_data = {"name": "Updated Name"}
        response = client.patch(f"/api/v1/connections/{connection.id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["type"] == "email_imap"  # Unchanged

    def test_update_connection_provider(self, client, test_db):
        """Test updating connection provider."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
            provider="generic",
        )
        test_db.commit()

        update_data = {"provider": "gmail"}
        response = client.patch(f"/api/v1/connections/{connection.id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["provider"] == "gmail"

    def test_update_connection_config(self, client, test_db):
        """Test updating connection config (re-encrypts credentials)."""
        from reconly_core.services.connection_service import create_connection, get_connection_decrypted

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.old.com", "username": "old", "password": "old_pass"},
        )
        test_db.commit()

        update_data = {
            "config": {
                "host": "imap.new.com",
                "port": 993,
                "username": "new@example.com",
                "password": "new_pass",
                "use_ssl": True,
            }
        }
        response = client.patch(f"/api/v1/connections/{connection.id}", json=update_data)
        assert response.status_code == 200

        # Expire cached objects so we re-read from DB (the API route used a different session)
        test_db.expire_all()

        # Verify config was updated by decrypting it from DB
        decrypted = get_connection_decrypted(test_db, connection.id)
        assert decrypted["host"] == "imap.new.com"
        assert decrypted["username"] == "new@example.com"
        assert decrypted["password"] == "new_pass"

    def test_update_connection_partial_update(self, client, test_db):
        """Test partial update only changes specified fields."""
        from reconly_core.services.connection_service import create_connection, get_connection_decrypted

        connection = create_connection(
            db=test_db,
            name="Original Name",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
            provider="generic",
        )
        test_db.commit()

        # Only update name
        update_data = {"name": "New Name"}
        response = client.patch(f"/api/v1/connections/{connection.id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "New Name"
        assert data["provider"] == "generic"  # Unchanged

        # Verify config is unchanged
        decrypted = get_connection_decrypted(test_db, connection.id)
        assert decrypted["host"] == "imap.test.com"
        assert decrypted["password"] == "pass"

    def test_update_connection_not_found(self, client):
        """Test updating a non-existent connection."""
        response = client.patch("/api/v1/connections/99999", json={"name": "New Name"})
        assert response.status_code == 404
        assert "Connection not found" in response.text


@pytest.mark.api
class TestDeleteConnection:
    """Test DELETE /api/v1/connections/{id} endpoint."""

    def test_delete_connection_success(self, client, test_db):
        """Test deleting a connection that is not in use."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        test_db.commit()
        connection_id = connection.id

        response = client.delete(f"/api/v1/connections/{connection_id}")
        assert response.status_code == 204

        # Verify connection is deleted
        response = client.get(f"/api/v1/connections/{connection_id}")
        assert response.status_code == 404

    def test_delete_connection_not_found(self, client):
        """Test deleting a non-existent connection."""
        response = client.delete("/api/v1/connections/99999")
        assert response.status_code == 404

    def test_delete_connection_in_use_raises_error(self, client, test_db):
        """Test that deleting a connection in use by sources returns 409."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        test_db.commit()

        # Create sources using the connection
        source1 = Source(
            name="Source 1",
            type="imap",
            url="imap://test1",
            connection_id=connection.id,
            enabled=True,
        )
        source2 = Source(
            name="Source 2",
            type="imap",
            url="imap://test2",
            connection_id=connection.id,
            enabled=True,
        )
        test_db.add_all([source1, source2])
        test_db.commit()

        # Try to delete without force
        response = client.delete(f"/api/v1/connections/{connection.id}")
        assert response.status_code == 409
        assert "in use by 2 source(s)" in response.text
        assert "Source 1" in response.text
        assert "force=true" in response.text

    def test_delete_connection_in_use_with_force(self, client, test_db):
        """Test that force=true allows deleting a connection in use."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "test", "password": "pass"},
        )
        test_db.commit()

        # Create a source using the connection
        source = Source(
            name="Test Source",
            type="imap",
            url="imap://test",
            connection_id=connection.id,
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        source_id = source.id

        # Delete with force=true
        response = client.delete(f"/api/v1/connections/{connection.id}?force=true")
        assert response.status_code == 204

        # Verify connection is deleted
        response = client.get(f"/api/v1/connections/{connection.id}")
        assert response.status_code == 404

        # Verify source's connection_id is set to NULL
        test_db.expire_all()
        source = test_db.query(Source).filter(Source.id == source_id).first()
        assert source is not None
        assert source.connection_id is None


@pytest.mark.api
class TestTestConnection:
    """Test POST /api/v1/connections/{id}/test endpoint."""

    def test_test_imap_connection_success(self, client, test_db):
        """Test IMAP connection test with successful connection."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={
                "host": "imap.gmail.com",
                "port": 993,
                "username": "test@gmail.com",
                "password": "app_password",
                "use_ssl": True,
            },
        )
        test_db.commit()

        # Mock the IMAP test to succeed
        with patch("reconly_api.routes.connections._test_imap_connection") as mock_test:
            from reconly_api.schemas.connections import ConnectionTestResult

            mock_test.return_value = ConnectionTestResult(
                success=True,
                message="Successfully connected to IMAP server and authenticated.",
            )

            response = client.post(f"/api/v1/connections/{connection.id}/test")
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert "Successfully connected" in data["message"]
            assert "response_time_ms" in data

        # Verify health was updated
        test_db.refresh(connection)
        assert connection.last_check_at is not None
        assert connection.last_success_at is not None

    def test_test_imap_connection_failure(self, client, test_db):
        """Test IMAP connection test with failed connection."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="Test Connection",
            connection_type="email_imap",
            config={
                "host": "imap.invalid.com",
                "port": 993,
                "username": "test@invalid.com",
                "password": "wrong_password",
                "use_ssl": True,
            },
        )
        test_db.commit()

        # Mock the IMAP test to fail
        with patch("reconly_api.routes.connections._test_imap_connection") as mock_test:
            from reconly_api.schemas.connections import ConnectionTestResult

            mock_test.return_value = ConnectionTestResult(
                success=False,
                message="Authentication failed. Please check username and password.",
            )

            response = client.post(f"/api/v1/connections/{connection.id}/test")
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is False
            assert "Authentication failed" in data["message"]

        # Verify health was updated with failure
        test_db.refresh(connection)
        assert connection.last_check_at is not None
        assert connection.last_failure_at is not None

    def test_test_http_basic_connection(self, client, test_db):
        """Test HTTP Basic auth connection test."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="HTTP Basic Auth",
            connection_type="http_basic",
            config={
                "username": "api_user",
                "password": "api_password",
            },
        )
        test_db.commit()

        response = client.post(f"/api/v1/connections/{connection.id}/test")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "credentials are configured" in data["message"]

    def test_test_api_key_connection(self, client, test_db):
        """Test API key connection test."""
        from reconly_core.services.connection_service import create_connection

        connection = create_connection(
            db=test_db,
            name="API Key",
            connection_type="api_key",
            config={
                "api_key": "sk-test123",
                "endpoint": "https://api.example.com",
            },
        )
        test_db.commit()

        response = client.post(f"/api/v1/connections/{connection.id}/test")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "API key is configured" in data["message"]

    def test_test_connection_not_found(self, client):
        """Test testing a non-existent connection."""
        response = client.post("/api/v1/connections/99999/test")
        assert response.status_code == 404
        assert "Connection not found" in response.text

    def test_test_connection_unsupported_type(self, client, test_db):
        """Test testing a connection with unsupported type."""
        from reconly_core.services.connection_service import create_connection

        # Create a connection with OAuth type (not directly testable)
        connection = create_connection(
            db=test_db,
            name="OAuth Connection",
            connection_type="email_oauth",
            config={"provider": "gmail", "access_token": "token123"},
        )
        test_db.commit()

        response = client.post(f"/api/v1/connections/{connection.id}/test")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert "not supported" in data["message"]
