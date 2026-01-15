"""Tests for IMAP Source API routes.

Tests the IMAP-specific source creation endpoints and OAuth flow integration.
"""
from unittest.mock import patch

import pytest

from reconly_core.database.models import OAuthCredential, Source


@pytest.fixture(autouse=True)
def set_secret_key(monkeypatch):
    """Set SECRET_KEY for all tests in this module."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-imap-tests-minimum-32-chars")


@pytest.mark.api
class TestIMAPSourceCreation:
    """Test suite for IMAP source creation via POST /api/v1/sources/imap."""

    def test_create_generic_imap_source(self, client, test_db):
        """Test creating a generic IMAP source with password encryption."""
        source_data = {
            "name": "Generic IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "imap_username": "test@example.com",
            "imap_password": "secret123",
            "imap_use_ssl": True,
            "folders": ["INBOX", "Archive"],
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        assert data["message"] == "IMAP source created successfully."
        assert data["oauth_url"] is None

        # Verify source data
        source = data["source"]
        assert source["name"] == "Generic IMAP"
        assert source["type"] == "imap"
        assert source["url"] == "imap://mail.example.com:993"
        assert source["auth_status"] == "active"
        assert source["enabled"] is True

        # Verify config has provider and folders
        config = source["config"]
        assert config["provider"] == "generic"
        assert config["folders"] == ["INBOX", "Archive"]
        assert config["imap_host"] == "mail.example.com"
        assert config["imap_port"] == 993
        assert config["imap_username"] == "test@example.com"
        assert config["imap_use_ssl"] is True

        # Verify password is NOT in response
        assert "imap_password" not in config
        assert "password" not in config

        # Verify password is encrypted in database
        db_source = test_db.query(Source).filter(Source.id == source["id"]).first()
        assert "imap_password_encrypted" in db_source.config
        assert db_source.config["imap_password_encrypted"] != "secret123"

    def test_create_generic_imap_with_default_folder(self, client, test_db):
        """Test creating generic IMAP source without specifying folders (defaults to INBOX)."""
        source_data = {
            "name": "Default Folder IMAP",
            "provider": "generic",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_username": "user@example.com",
            "imap_password": "pass123",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        source = data["source"]
        assert source["config"]["folders"] == ["INBOX"]

    def test_create_generic_imap_with_filters(self, client, test_db):
        """Test creating generic IMAP with email filters (from, subject)."""
        source_data = {
            "name": "Filtered IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "imap_username": "test@example.com",
            "imap_password": "secret123",
            "from_filter": "newsletter@example.com",
            "subject_filter": "Weekly Update",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        config = data["source"]["config"]
        assert config["from_filter"] == "newsletter@example.com"
        assert config["subject_filter"] == "Weekly Update"

    def test_create_generic_imap_with_content_filters(self, client, test_db):
        """Test creating generic IMAP with content filtering keywords."""
        source_data = {
            "name": "Content Filtered IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "imap_username": "test@example.com",
            "imap_password": "secret123",
            "include_keywords": ["python", "ai"],
            "exclude_keywords": ["spam"],
            "filter_mode": "content",
            "use_regex": False,
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        source = data["source"]
        assert source["include_keywords"] == ["python", "ai"]
        assert source["exclude_keywords"] == ["spam"]
        assert source["filter_mode"] == "content"
        assert source["use_regex"] is False

    def test_create_generic_imap_missing_required_fields(self, client):
        """Test that creating generic IMAP without required fields fails."""
        # Missing imap_host
        response = client.post("/api/v1/sources/imap", json={
            "name": "Incomplete IMAP",
            "provider": "generic",
            "imap_username": "test@example.com",
            "imap_password": "secret123",
        })
        assert response.status_code == 422
        assert "imap_host is required" in response.text

        # Missing imap_username
        response = client.post("/api/v1/sources/imap", json={
            "name": "Incomplete IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_password": "secret123",
        })
        assert response.status_code == 422
        assert "imap_username is required" in response.text

        # Missing imap_password
        response = client.post("/api/v1/sources/imap", json={
            "name": "Incomplete IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_username": "test@example.com",
        })
        assert response.status_code == 422
        assert "imap_password is required" in response.text

    def test_create_generic_imap_without_secret_key(self, client, monkeypatch):
        """Test that IMAP creation fails gracefully if SECRET_KEY is not set."""
        # Clear SECRET_KEY
        monkeypatch.delenv("SECRET_KEY", raising=False)

        source_data = {
            "name": "Generic IMAP",
            "provider": "generic",
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "imap_username": "test@example.com",
            "imap_password": "secret123",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 500
        assert "Failed to encrypt credentials" in response.text


@pytest.mark.api
class TestIMAPSourceOAuth:
    """Test suite for OAuth-based IMAP sources (Gmail, Outlook)."""

    @patch("reconly_api.routes.sources._is_oauth_provider_configured")
    @patch("reconly_api.routes.sources.generate_gmail_auth_url")
    @patch("reconly_api.routes.sources.create_oauth_state")
    def test_create_gmail_source_returns_oauth_url(
        self,
        mock_create_state,
        mock_generate_url,
        mock_is_configured,
        client,
        test_db,
    ):
        """Test creating Gmail source returns OAuth URL and pending status."""
        # Mock OAuth configuration
        mock_is_configured.return_value = True
        mock_create_state.return_value = ("state123", "verifier", "challenge")
        mock_generate_url.return_value = "https://accounts.google.com/oauth?state=state123"

        source_data = {
            "name": "My Gmail",
            "provider": "gmail",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        assert data["oauth_url"] == "https://accounts.google.com/oauth?state=state123"
        assert "Complete OAuth authentication" in data["message"]

        # Verify source data
        source = data["source"]
        assert source["name"] == "My Gmail"
        assert source["type"] == "imap"
        assert source["url"] == "gmail://"
        assert source["auth_status"] == "pending_oauth"
        assert source["enabled"] is True

        # Verify config
        config = source["config"]
        assert config["provider"] == "gmail"
        assert config["folders"] == ["INBOX"]

        # Verify no OAuth credential created yet
        assert source["oauth_credential_id"] is None

        # Verify create_oauth_state was called with source ID
        mock_create_state.assert_called_once()
        call_args = mock_create_state.call_args[0]
        assert call_args[0] == source["id"]  # source_id
        assert call_args[1] == "gmail"  # provider

    @patch("reconly_api.routes.sources._is_oauth_provider_configured")
    @patch("reconly_api.routes.sources.generate_outlook_auth_url")
    @patch("reconly_api.routes.sources.create_oauth_state")
    def test_create_outlook_source_returns_oauth_url(
        self,
        mock_create_state,
        mock_generate_url,
        mock_is_configured,
        client,
        test_db,
    ):
        """Test creating Outlook source returns OAuth URL and pending status."""
        # Mock OAuth configuration
        mock_is_configured.return_value = True
        mock_create_state.return_value = ("state456", "verifier", "challenge")
        mock_generate_url.return_value = "https://login.microsoftonline.com/oauth?state=state456"

        source_data = {
            "name": "My Outlook",
            "provider": "outlook",
            "folders": ["Inbox", "Important"],
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 201

        data = response.json()
        assert data["oauth_url"] == "https://login.microsoftonline.com/oauth?state=state456"

        # Verify source data
        source = data["source"]
        assert source["name"] == "My Outlook"
        assert source["url"] == "outlook://"
        assert source["auth_status"] == "pending_oauth"
        assert source["config"]["folders"] == ["Inbox", "Important"]

    @patch("reconly_api.routes.sources._is_oauth_provider_configured")
    def test_create_gmail_source_unconfigured_oauth(
        self,
        mock_is_configured,
        client,
    ):
        """Test creating Gmail source fails if OAuth is not configured."""
        mock_is_configured.return_value = False

        source_data = {
            "name": "My Gmail",
            "provider": "gmail",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 503
        assert "Gmail OAuth is not configured" in response.text
        assert "GOOGLE_CLIENT_ID" in response.text

    @patch("reconly_api.routes.sources._is_oauth_provider_configured")
    def test_create_outlook_source_unconfigured_oauth(
        self,
        mock_is_configured,
        client,
    ):
        """Test creating Outlook source fails if OAuth is not configured."""
        mock_is_configured.return_value = False

        source_data = {
            "name": "My Outlook",
            "provider": "outlook",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 503
        assert "Outlook OAuth is not configured" in response.text
        assert "MICROSOFT_CLIENT_ID" in response.text

    @patch("reconly_api.routes.sources._is_oauth_provider_configured")
    @patch("reconly_api.routes.sources.create_oauth_state")
    def test_create_gmail_source_oauth_url_generation_fails(
        self,
        mock_create_state,
        mock_is_configured,
        client,
        test_db,
    ):
        """Test that source creation is rolled back if OAuth URL generation fails."""
        mock_is_configured.return_value = True
        mock_create_state.side_effect = Exception("OAuth state error")

        source_data = {
            "name": "My Gmail",
            "provider": "gmail",
        }

        response = client.post("/api/v1/sources/imap", json=source_data)
        assert response.status_code == 500
        assert "Failed to generate OAuth authorization URL" in response.text

        # Verify no source was created
        sources = test_db.query(Source).filter(Source.name == "My Gmail").all()
        assert len(sources) == 0


@pytest.mark.api
class TestIMAPSourceDeletion:
    """Test suite for IMAP source deletion and OAuth credential cascade."""

    def test_delete_generic_imap_source(self, client, test_db):
        """Test deleting a generic IMAP source."""
        # Create a generic IMAP source directly in database
        source = Source(
            name="Test IMAP",
            type="imap",
            url="imap://mail.example.com",
            config={
                "provider": "generic",
                "imap_host": "mail.example.com",
                "imap_port": 993,
                "folders": ["INBOX"],
            },
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)
        source_id = source.id

        # Delete the source
        delete_response = client.delete(f"/api/v1/sources/{source_id}")
        assert delete_response.status_code == 204

        # Verify source is deleted
        get_response = client.get(f"/api/v1/sources/{source_id}")
        assert get_response.status_code == 404

    def test_delete_oauth_imap_source_cascades_credentials(self, client, test_db):
        """Test deleting OAuth IMAP source also deletes OAuth credentials."""
        # Create a source with OAuth credentials
        source = Source(
            name="Gmail Source",
            type="imap",
            url="gmail://",
            config={"provider": "gmail", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        # Create OAuth credential for the source
        oauth_cred = OAuthCredential(
            source_id=source.id,
            provider="gmail",
            access_token_encrypted="encrypted_access_token",
            refresh_token_encrypted="encrypted_refresh_token",
            expires_at=None,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        test_db.add(oauth_cred)
        test_db.commit()
        test_db.refresh(oauth_cred)

        # Verify credential exists
        assert test_db.query(OAuthCredential).filter(
            OAuthCredential.source_id == source.id
        ).first() is not None

        # Delete the source
        response = client.delete(f"/api/v1/sources/{source.id}")
        assert response.status_code == 204

        # Verify OAuth credential is also deleted (CASCADE)
        assert test_db.query(OAuthCredential).filter(
            OAuthCredential.source_id == source.id
        ).first() is None

    def test_delete_nonexistent_imap_source(self, client):
        """Test deleting non-existent IMAP source returns 404."""
        response = client.delete("/api/v1/sources/99999")
        assert response.status_code == 404


@pytest.mark.api
class TestIMAPSourceListing:
    """Test suite for listing IMAP sources with auth_status."""

    def test_list_sources_includes_auth_status(self, client, test_db):
        """Test that source listing includes auth_status for IMAP sources."""
        # Create a generic IMAP source
        generic_source = Source(
            name="Generic IMAP",
            type="imap",
            url="imap://mail.example.com",
            config={"provider": "generic", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(generic_source)

        # Create a Gmail source with pending OAuth
        gmail_source = Source(
            name="Gmail",
            type="imap",
            url="gmail://",
            config={"provider": "gmail", "folders": ["INBOX"]},
            auth_status="pending_oauth",
            enabled=True,
        )
        test_db.add(gmail_source)

        # Create an RSS source (non-IMAP)
        rss_source = Source(
            name="RSS Feed",
            type="rss",
            url="https://example.com/feed.xml",
            enabled=True,
        )
        test_db.add(rss_source)

        test_db.commit()

        # List all sources
        response = client.get("/api/v1/sources")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 3

        # Find each source and verify auth_status
        generic = next(s for s in data if s["name"] == "Generic IMAP")
        assert generic["auth_status"] == "active"
        assert generic["type"] == "imap"

        gmail = next(s for s in data if s["name"] == "Gmail")
        assert gmail["auth_status"] == "pending_oauth"
        assert gmail["type"] == "imap"

        rss = next(s for s in data if s["name"] == "RSS Feed")
        assert rss["auth_status"] is None  # Non-IMAP sources have no auth_status
        assert rss["type"] == "rss"

    def test_list_sources_excludes_sensitive_data(self, client, test_db):
        """Test that source listing excludes passwords and tokens from config."""
        # Create a generic IMAP source
        source = Source(
            name="Generic IMAP",
            type="imap",
            url="imap://mail.example.com",
            config={
                "provider": "generic",
                "folders": ["INBOX"],
                "imap_host": "mail.example.com",
                "imap_username": "test@example.com",
                "imap_password_encrypted": "encrypted_password_blob",
            },
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()

        # List sources
        response = client.get("/api/v1/sources")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1

        config = data[0]["config"]
        # Verify sensitive fields are excluded
        assert "imap_password" not in config
        assert "imap_password_encrypted" not in config
        assert "password" not in config
        assert "access_token" not in config
        assert "refresh_token" not in config

        # Verify non-sensitive fields are present
        assert config["provider"] == "generic"
        assert config["imap_host"] == "mail.example.com"
        assert config["imap_username"] == "test@example.com"

    def test_get_source_includes_auth_status(self, client, test_db):
        """Test that getting a single source includes auth_status."""
        source = Source(
            name="Gmail Source",
            type="imap",
            url="gmail://",
            config={"provider": "gmail", "folders": ["INBOX"]},
            auth_status="pending_oauth",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        response = client.get(f"/api/v1/sources/{source.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == source.id
        assert data["name"] == "Gmail Source"
        assert data["auth_status"] == "pending_oauth"
        assert data["type"] == "imap"

    def test_get_source_includes_oauth_credential_id(self, client, test_db):
        """Test that getting a source includes oauth_credential_id if present."""
        # Create source
        source = Source(
            name="Gmail Source",
            type="imap",
            url="gmail://",
            config={"provider": "gmail", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        # Create OAuth credential
        oauth_cred = OAuthCredential(
            source_id=source.id,
            provider="gmail",
            access_token_encrypted="encrypted_access_token",
            refresh_token_encrypted="encrypted_refresh_token",
            expires_at=None,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        test_db.add(oauth_cred)
        test_db.commit()
        test_db.refresh(oauth_cred)

        response = client.get(f"/api/v1/sources/{source.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["oauth_credential_id"] == oauth_cred.id

    def test_filter_sources_by_imap_type(self, client, test_db):
        """Test filtering sources by IMAP type."""
        # Create IMAP source
        imap_source = Source(
            name="IMAP Source",
            type="imap",
            url="imap://mail.example.com",
            config={"provider": "generic", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(imap_source)

        # Create RSS source
        rss_source = Source(
            name="RSS Source",
            type="rss",
            url="https://example.com/feed.xml",
            enabled=True,
        )
        test_db.add(rss_source)

        test_db.commit()

        # Filter by IMAP
        response = client.get("/api/v1/sources?type=imap")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "imap"
        assert data[0]["name"] == "IMAP Source"


@pytest.mark.api
class TestIMAPSourceUpdate:
    """Test suite for updating IMAP sources."""

    def test_update_imap_source_name(self, client, test_db):
        """Test updating IMAP source name."""
        # Create source
        source = Source(
            name="Original Name",
            type="imap",
            url="imap://mail.example.com",
            config={"provider": "generic", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        # Update name
        response = client.patch(f"/api/v1/sources/{source.id}", json={
            "name": "Updated Name"
        })
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["type"] == "imap"

    def test_update_imap_source_enabled_status(self, client, test_db):
        """Test toggling IMAP source enabled status."""
        # Create source
        source = Source(
            name="Test IMAP",
            type="imap",
            url="imap://mail.example.com",
            config={"provider": "generic", "folders": ["INBOX"]},
            auth_status="active",
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        # Disable source
        response = client.patch(f"/api/v1/sources/{source.id}", json={
            "enabled": False
        })
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Re-enable source
        response = client.patch(f"/api/v1/sources/{source.id}", json={
            "enabled": True
        })
        assert response.status_code == 200
        assert response.json()["enabled"] is True
