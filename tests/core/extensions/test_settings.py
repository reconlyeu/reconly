"""Tests for extension settings functionality."""
import pytest
from unittest.mock import MagicMock, patch

from reconly_core.extensions.settings import (
    get_extension_settings_prefix,
    get_extension_enabled_key,
    is_extension_enabled,
    is_extension_configured,
    can_enable_extension,
    set_extension_enabled,
    get_extension_activation_state,
    register_extension_settings,
)
from reconly_core.extensions.types import ExtensionType
from reconly_core.services.settings_registry import SETTINGS_REGISTRY, SettingDef


def make_setting_def(
    category="extension",
    type_=bool,
    default=False,
    editable=True,
    env_var="",
    secret=False,
    description="",
):
    """Helper to create SettingDef with all required args."""
    return SettingDef(
        category=category,
        type=type_,
        default=default,
        editable=editable,
        env_var=env_var,
        secret=secret,
        description=description,
    )


class TestGetExtensionSettingsPrefix:
    """Tests for get_extension_settings_prefix function."""

    def test_exporter_prefix(self):
        """Test exporter prefix matches built-in pattern."""
        prefix = get_extension_settings_prefix(ExtensionType.EXPORTER, "notion")
        assert prefix == "export.notion"

    def test_fetcher_prefix(self):
        """Test fetcher prefix matches built-in pattern."""
        prefix = get_extension_settings_prefix(ExtensionType.FETCHER, "reddit")
        assert prefix == "fetch.reddit"

    def test_provider_prefix(self):
        """Test provider prefix matches built-in pattern."""
        prefix = get_extension_settings_prefix(ExtensionType.PROVIDER, "gemini")
        assert prefix == "provider.gemini"


class TestGetExtensionEnabledKey:
    """Tests for get_extension_enabled_key function."""

    def test_exporter_enabled_key(self):
        """Test enabled key for exporter."""
        key = get_extension_enabled_key(ExtensionType.EXPORTER, "notion")
        assert key == "export.notion.enabled"

    def test_fetcher_enabled_key(self):
        """Test enabled key for fetcher."""
        key = get_extension_enabled_key(ExtensionType.FETCHER, "reddit")
        assert key == "fetch.reddit.enabled"


class TestIsExtensionEnabled:
    """Tests for is_extension_enabled function."""

    def setup_method(self):
        """Store original registry state."""
        self._original_registry = SETTINGS_REGISTRY.copy()

    def teardown_method(self):
        """Restore original registry."""
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - set(self._original_registry.keys())
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_enabled_from_settings(self, mock_service_cls):
        """Test enabled state read from settings service."""
        mock_service = MagicMock()
        mock_service.get.return_value = True
        mock_service_cls.return_value = mock_service

        # Register the setting
        SETTINGS_REGISTRY["export.test.enabled"] = make_setting_def()

        mock_db = MagicMock()
        result = is_extension_enabled(ExtensionType.EXPORTER, "test", mock_db)

        assert result is True
        mock_service.get.assert_called_once_with("export.test.enabled")

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_disabled_from_settings(self, mock_service_cls):
        """Test disabled state read from settings service."""
        mock_service = MagicMock()
        mock_service.get.return_value = False
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test2.enabled"] = make_setting_def()

        mock_db = MagicMock()
        result = is_extension_enabled(ExtensionType.EXPORTER, "test2", mock_db)

        assert result is False

    def test_default_enabled_when_no_registry(self):
        """Test returns True when setting not in registry."""
        mock_db = MagicMock()
        result = is_extension_enabled(ExtensionType.EXPORTER, "unregistered", mock_db)

        # Default is True for extensions without explicit settings
        assert result is True


class TestIsExtensionConfigured:
    """Tests for is_extension_configured function."""

    def setup_method(self):
        """Store original registry state."""
        self._original_registry = SETTINGS_REGISTRY.copy()

    def teardown_method(self):
        """Restore original registry."""
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - set(self._original_registry.keys())
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    def test_no_required_fields_returns_true(self):
        """Test returns True when no required fields."""
        mock_db = MagicMock()
        result = is_extension_configured(ExtensionType.EXPORTER, "test", mock_db, [])
        assert result is True

        result = is_extension_configured(ExtensionType.EXPORTER, "test", mock_db, None)
        assert result is True

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_all_required_fields_set(self, mock_service_cls):
        """Test returns True when all required fields have values."""
        mock_service = MagicMock()
        mock_service.get.side_effect = lambda key: {
            "export.test.api_key": "secret123",
            "export.test.path": "/some/path",
        }.get(key)
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test.api_key"] = make_setting_def(type_=str, default=None)
        SETTINGS_REGISTRY["export.test.path"] = make_setting_def(type_=str, default=None)

        mock_db = MagicMock()
        result = is_extension_configured(
            ExtensionType.EXPORTER, "test", mock_db, ["api_key", "path"]
        )

        assert result is True

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_required_field_missing(self, mock_service_cls):
        """Test returns False when required field has no value."""
        mock_service = MagicMock()
        mock_service.get.return_value = None
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test.api_key"] = make_setting_def(type_=str, default=None)

        mock_db = MagicMock()
        result = is_extension_configured(
            ExtensionType.EXPORTER, "test", mock_db, ["api_key"]
        )

        assert result is False

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_required_field_empty_string(self, mock_service_cls):
        """Test returns False when required field is empty string."""
        mock_service = MagicMock()
        mock_service.get.return_value = ""
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test.path"] = make_setting_def(type_=str, default=None)

        mock_db = MagicMock()
        result = is_extension_configured(
            ExtensionType.EXPORTER, "test", mock_db, ["path"]
        )

        assert result is False

    def test_field_not_in_registry(self):
        """Test returns False when field not registered."""
        mock_db = MagicMock()
        result = is_extension_configured(
            ExtensionType.EXPORTER, "test", mock_db, ["unregistered_field"]
        )

        assert result is False


class TestCanEnableExtension:
    """Tests for can_enable_extension function."""

    def test_no_required_fields(self):
        """Test can enable when no required fields."""
        mock_db = MagicMock()
        result = can_enable_extension(ExtensionType.EXPORTER, "test", mock_db, [])
        assert result is True

        result = can_enable_extension(ExtensionType.EXPORTER, "test", mock_db, None)
        assert result is True

    @patch('reconly_core.extensions.settings.is_extension_configured')
    def test_delegates_to_is_configured(self, mock_is_configured):
        """Test delegates to is_extension_configured when has required fields."""
        mock_is_configured.return_value = True

        mock_db = MagicMock()
        result = can_enable_extension(
            ExtensionType.EXPORTER, "test", mock_db, ["field1"]
        )

        assert result is True
        mock_is_configured.assert_called_once()


class TestSetExtensionEnabled:
    """Tests for set_extension_enabled function."""

    def setup_method(self):
        """Store original registry state."""
        self._original_registry = SETTINGS_REGISTRY.copy()

    def teardown_method(self):
        """Restore original registry."""
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - set(self._original_registry.keys())
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_set_enabled_true(self, mock_service_cls):
        """Test setting enabled to True."""
        mock_service = MagicMock()
        mock_service.set.return_value = True
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test.enabled"] = make_setting_def()

        mock_db = MagicMock()
        result = set_extension_enabled(ExtensionType.EXPORTER, "test", True, mock_db)

        assert result is True
        mock_service.set.assert_called_once_with("export.test.enabled", True)

    @patch('reconly_core.services.settings_service.SettingsService')
    def test_set_enabled_false(self, mock_service_cls):
        """Test setting enabled to False."""
        mock_service = MagicMock()
        mock_service.set.return_value = True
        mock_service_cls.return_value = mock_service

        SETTINGS_REGISTRY["export.test.enabled"] = make_setting_def(default=True)

        mock_db = MagicMock()
        result = set_extension_enabled(ExtensionType.EXPORTER, "test", False, mock_db)

        assert result is True
        mock_service.set.assert_called_once_with("export.test.enabled", False)

    def test_raises_when_not_registered(self):
        """Test raises KeyError when setting not registered."""
        mock_db = MagicMock()

        with pytest.raises(KeyError) as exc_info:
            set_extension_enabled(
                ExtensionType.EXPORTER, "unregistered", True, mock_db
            )

        assert "not registered" in str(exc_info.value)


class TestGetExtensionActivationState:
    """Tests for get_extension_activation_state function."""

    @patch('reconly_core.extensions.settings.is_extension_enabled')
    @patch('reconly_core.extensions.settings.is_extension_configured')
    @patch('reconly_core.extensions.settings.can_enable_extension')
    def test_returns_all_states(self, mock_can, mock_configured, mock_enabled):
        """Test returns dict with all activation states."""
        mock_enabled.return_value = True
        mock_configured.return_value = True
        mock_can.return_value = True

        mock_db = MagicMock()
        state = get_extension_activation_state(
            ExtensionType.EXPORTER, "test", mock_db, ["field1"]
        )

        assert state == {
            "enabled": True,
            "is_configured": True,
            "can_enable": True,
        }

    @patch('reconly_core.extensions.settings.is_extension_enabled')
    @patch('reconly_core.extensions.settings.is_extension_configured')
    @patch('reconly_core.extensions.settings.can_enable_extension')
    def test_unconfigured_extension(self, mock_can, mock_configured, mock_enabled):
        """Test state for unconfigured extension."""
        mock_enabled.return_value = False
        mock_configured.return_value = False
        mock_can.return_value = False

        mock_db = MagicMock()
        state = get_extension_activation_state(
            ExtensionType.EXPORTER, "test", mock_db, ["required_field"]
        )

        assert state["enabled"] is False
        assert state["is_configured"] is False
        assert state["can_enable"] is False


class TestRegisterExtensionSettings:
    """Tests for register_extension_settings function."""

    def setup_method(self):
        """Store original registry state."""
        self._original_registry = SETTINGS_REGISTRY.copy()

    def teardown_method(self):
        """Restore original registry."""
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - set(self._original_registry.keys())
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    def test_registers_enabled_setting(self):
        """Test always registers enabled setting."""
        register_extension_settings(ExtensionType.EXPORTER, "new_ext")

        assert "export.new_ext.enabled" in SETTINGS_REGISTRY

        setting = SETTINGS_REGISTRY["export.new_ext.enabled"]
        assert setting.type is bool
        assert setting.editable is True

    def test_enabled_default_true_when_no_required(self):
        """Test enabled defaults to True when no required fields."""
        register_extension_settings(ExtensionType.EXPORTER, "no_req", [])

        setting = SETTINGS_REGISTRY["export.no_req.enabled"]
        assert setting.default is True

    def test_enabled_default_false_when_has_required(self):
        """Test enabled defaults to False when has required fields."""
        register_extension_settings(
            ExtensionType.EXPORTER,
            "has_req",
            [{"key": "api_key", "required": True}]
        )

        setting = SETTINGS_REGISTRY["export.has_req.enabled"]
        assert setting.default is False

    def test_registers_config_fields(self):
        """Test registers config fields from list."""
        config_fields = [
            {
                "key": "api_key",
                "type": "string",
                "default": None,
                "required": True,
                "description": "API key for service",
            },
            {
                "key": "enabled_feature",
                "type": "boolean",
                "default": True,
                "required": False,
                "description": "Enable feature",
            },
            {
                "key": "max_items",
                "type": "integer",
                "default": 10,
                "required": False,
                "description": "Maximum items",
            },
            {
                "key": "output_path",
                "type": "path",
                "default": "/tmp",
                "required": False,
                "description": "Output path",
            },
        ]

        register_extension_settings(ExtensionType.EXPORTER, "full", config_fields)

        # Check api_key
        assert "export.full.api_key" in SETTINGS_REGISTRY
        api_setting = SETTINGS_REGISTRY["export.full.api_key"]
        assert api_setting.type is str
        assert api_setting.default is None
        assert api_setting.description == "API key for service"

        # Check boolean
        assert "export.full.enabled_feature" in SETTINGS_REGISTRY
        bool_setting = SETTINGS_REGISTRY["export.full.enabled_feature"]
        assert bool_setting.type is bool
        assert bool_setting.default is True

        # Check integer
        assert "export.full.max_items" in SETTINGS_REGISTRY
        int_setting = SETTINGS_REGISTRY["export.full.max_items"]
        assert int_setting.type is int
        assert int_setting.default == 10

        # Check path (stored as str)
        assert "export.full.output_path" in SETTINGS_REGISTRY
        path_setting = SETTINGS_REGISTRY["export.full.output_path"]
        assert path_setting.type is str
        assert path_setting.default == "/tmp"

    def test_does_not_overwrite_existing(self):
        """Test does not overwrite existing registry entries."""
        # Pre-register a setting
        SETTINGS_REGISTRY["export.existing.enabled"] = make_setting_def(
            category="test",
            default=True,
            editable=False,
            description="Pre-existing",
        )

        register_extension_settings(ExtensionType.EXPORTER, "existing")

        # Should not have been overwritten
        setting = SETTINGS_REGISTRY["export.existing.enabled"]
        assert setting.description == "Pre-existing"
        assert setting.editable is False

    def test_secret_field(self):
        """Test secret field is registered correctly."""
        config_fields = [
            {
                "key": "secret_key",
                "type": "string",
                "secret": True,
                "description": "Secret value",
            }
        ]

        register_extension_settings(ExtensionType.EXPORTER, "secret_ext", config_fields)

        setting = SETTINGS_REGISTRY["export.secret_ext.secret_key"]
        assert setting.secret is True

    def test_fetcher_settings(self):
        """Test registering fetcher settings uses fetch prefix."""
        register_extension_settings(ExtensionType.FETCHER, "reddit")

        assert "fetch.reddit.enabled" in SETTINGS_REGISTRY

    def test_provider_settings(self):
        """Test registering provider settings uses provider prefix."""
        register_extension_settings(ExtensionType.PROVIDER, "gemini")

        assert "provider.gemini.enabled" in SETTINGS_REGISTRY
