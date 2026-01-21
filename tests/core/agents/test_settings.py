"""Tests for AgentSettings validation and configuration."""
import os
import pytest
from unittest.mock import patch

from reconly_core.agents.settings import AgentSettings, AgentSettingsError
from reconly_core.services.settings_service import SettingsService
from reconly_core.services.settings_registry import SETTINGS_REGISTRY


class TestAgentSettingsRegistry:
    """Tests for agent settings in the settings registry."""

    def test_agent_settings_are_registered(self):
        """All agent settings should be in the registry."""
        expected_keys = [
            "agent.search_provider",
            "agent.searxng_url",
            "agent.max_search_results",
            "agent.default_max_iterations",
        ]
        for key in expected_keys:
            assert key in SETTINGS_REGISTRY, f"Missing setting: {key}"

    def test_agent_settings_have_correct_category(self):
        """All agent settings should have category 'agent'."""
        agent_keys = [k for k in SETTINGS_REGISTRY if k.startswith("agent.")]
        for key in agent_keys:
            assert SETTINGS_REGISTRY[key].category == "agent"

    def test_search_provider_defaults_to_duckduckgo(self):
        """search_provider should default to duckduckgo (works without config)."""
        setting = SETTINGS_REGISTRY["agent.search_provider"]
        assert setting.default == "duckduckgo"

    def test_searxng_url_has_default(self):
        """searxng_url should have a sensible default."""
        setting = SETTINGS_REGISTRY["agent.searxng_url"]
        assert setting.default == "http://localhost:8080"

    def test_max_search_results_default(self):
        """max_search_results should default to 10."""
        setting = SETTINGS_REGISTRY["agent.max_search_results"]
        assert setting.default == 10
        assert setting.type is int

    def test_default_max_iterations_default(self):
        """default_max_iterations should default to 5."""
        setting = SETTINGS_REGISTRY["agent.default_max_iterations"]
        assert setting.default == 5
        assert setting.type is int


class TestAgentSettingsValidation:
    """Tests for AgentSettings.validate() method."""

    def test_validate_searxng_with_url_succeeds(self):
        """SearXNG provider with URL should validate successfully."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080",
        )
        settings.validate()  # Should not raise

    def test_validate_searxng_without_url_fails(self):
        """SearXNG provider without URL should fail validation."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="",
        )
        with pytest.raises(AgentSettingsError, match="SearXNG URL required"):
            settings.validate()

    def test_validate_searxng_with_none_url_fails(self):
        """SearXNG provider with None URL should fail validation."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url=None,
        )
        with pytest.raises(AgentSettingsError, match="SearXNG URL required"):
            settings.validate()

    def test_validate_invalid_provider_fails(self):
        """Invalid search provider should fail validation."""
        settings = AgentSettings(
            search_provider="invalid",
        )
        with pytest.raises(AgentSettingsError, match="Invalid search_provider"):
            settings.validate()

    def test_validate_max_search_results_zero_fails(self):
        """max_search_results of 0 should fail validation."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080",
            max_search_results=0,
        )
        with pytest.raises(AgentSettingsError, match="max_search_results must be at least 1"):
            settings.validate()

    def test_validate_max_search_results_negative_fails(self):
        """Negative max_search_results should fail validation."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080",
            max_search_results=-5,
        )
        with pytest.raises(AgentSettingsError, match="max_search_results must be at least 1"):
            settings.validate()

    def test_validate_default_max_iterations_zero_fails(self):
        """default_max_iterations of 0 should fail validation."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080",
            default_max_iterations=0,
        )
        with pytest.raises(AgentSettingsError, match="default_max_iterations must be at least 1"):
            settings.validate()

    def test_validate_duckduckgo_without_config_succeeds(self):
        """DuckDuckGo should validate without any configuration."""
        settings = AgentSettings(search_provider="duckduckgo")
        settings.validate()  # Should not raise

    def test_validate_tavily_requires_api_key(self):
        """Tavily should fail validation without API key."""
        settings = AgentSettings(search_provider="tavily")
        with pytest.raises(AgentSettingsError, match="Tavily API key required"):
            settings.validate()

    def test_validate_tavily_with_api_key_succeeds(self):
        """Tavily should validate with API key."""
        settings = AgentSettings(
            search_provider="tavily",
            tavily_api_key="tvly-test-key",
        )
        settings.validate()  # Should not raise

    def test_validate_tavily_with_empty_api_key_fails(self):
        """Tavily should fail validation with empty API key."""
        settings = AgentSettings(
            search_provider="tavily",
            tavily_api_key="",
        )
        with pytest.raises(AgentSettingsError, match="Tavily API key required"):
            settings.validate()


class TestAgentSettingsIsConfigured:
    """Tests for AgentSettings.is_configured() method."""

    def test_is_configured_returns_true_for_valid_searxng(self):
        """is_configured should return True for valid SearXNG config."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080",
        )
        assert settings.is_configured() is True

    def test_is_configured_returns_false_for_missing_searxng_url(self):
        """is_configured should return False when SearXNG URL is missing."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="",
        )
        assert settings.is_configured() is False

    def test_is_configured_returns_false_for_invalid_provider(self):
        """is_configured should return False for invalid provider."""
        settings = AgentSettings(
            search_provider="invalid",
        )
        assert settings.is_configured() is False


class TestAgentSettingsFromService:
    """Tests for AgentSettings.from_settings_service() method."""

    def test_from_settings_service_loads_defaults(self, db_session):
        """from_settings_service should load default values."""
        with patch.dict(os.environ, {}, clear=True):
            service = SettingsService(db_session)
            settings = AgentSettings.from_settings_service(service)

            assert settings.search_provider == "duckduckgo"
            assert settings.searxng_url == "http://localhost:8080"
            assert settings.max_search_results == 10
            assert settings.default_max_iterations == 5

    def test_from_settings_service_loads_env_values(self, db_session):
        """from_settings_service should load values from environment."""
        env_vars = {
            "AGENT_SEARCH_PROVIDER": "searxng",
            "SEARXNG_URL": "http://searxng.local:9090",
            "AGENT_MAX_SEARCH_RESULTS": "20",
            "AGENT_DEFAULT_MAX_ITERATIONS": "10",
        }
        with patch.dict(os.environ, env_vars):
            service = SettingsService(db_session)
            settings = AgentSettings.from_settings_service(service)

            assert settings.search_provider == "searxng"
            assert settings.searxng_url == "http://searxng.local:9090"
            assert settings.max_search_results == 20
            assert settings.default_max_iterations == 10

    def test_from_settings_service_loads_db_values(self, db_session):
        """from_settings_service should prefer DB values over defaults."""
        with patch.dict(os.environ, {}, clear=True):
            service = SettingsService(db_session)

            # Set values in database (only editable settings)
            service.set("agent.search_provider", "searxng")
            service.set("agent.searxng_url", "http://custom-searxng:8888")
            service.set("agent.max_search_results", 25)
            service.set("agent.default_max_iterations", 15)

            settings = AgentSettings.from_settings_service(service)

            assert settings.search_provider == "searxng"
            assert settings.searxng_url == "http://custom-searxng:8888"
            assert settings.max_search_results == 25
            assert settings.default_max_iterations == 15
