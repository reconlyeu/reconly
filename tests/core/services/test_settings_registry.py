"""Tests for settings registry functions, especially auto-registration."""
from reconly_core.services.settings_registry import (
    SETTINGS_REGISTRY,
    SettingDef,
    register_component_settings,
)
from reconly_core.exporters.base import ConfigField, ExporterConfigSchema


class TestRegisterComponentSettings:
    """Test cases for register_component_settings function."""

    def setup_method(self):
        """Store original registry entries to restore after tests."""
        self._original_keys = set(SETTINGS_REGISTRY.keys())

    def teardown_method(self):
        """Remove any settings added during tests."""
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - self._original_keys
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    def test_registers_enabled_setting(self):
        """Test that enabled setting is automatically registered."""
        schema = ExporterConfigSchema(fields=[], supports_direct_export=False)
        register_component_settings("export", "test-format", schema)

        assert "export.test-format.enabled" in SETTINGS_REGISTRY
        setting = SETTINGS_REGISTRY["export.test-format.enabled"]
        assert setting.type is bool
        assert setting.editable is True
        assert setting.category == "export"

    def test_enabled_default_true_when_no_required_fields(self):
        """Test that enabled defaults to True when no fields are required."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="optional_field",
                    type="string",
                    label="Optional",
                    description="An optional field",
                    required=False,
                )
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "no-required", schema)

        setting = SETTINGS_REGISTRY["export.no-required.enabled"]
        assert setting.default is True

    def test_enabled_default_false_when_has_required_fields(self):
        """Test that enabled defaults to False when there are required fields."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="required_path",
                    type="path",
                    label="Required Path",
                    description="A required path",
                    required=True,
                )
            ],
            supports_direct_export=True,
        )
        register_component_settings("export", "has-required", schema)

        setting = SETTINGS_REGISTRY["export.has-required.enabled"]
        assert setting.default is False

    def test_registers_all_schema_fields(self):
        """Test that all schema fields are registered as settings."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="vault_path",
                    type="path",
                    label="Vault Path",
                    description="Path to vault",
                    default=None,
                    required=True,
                ),
                ConfigField(
                    key="include_content",
                    type="boolean",
                    label="Include Content",
                    description="Include full content",
                    default=True,
                    required=False,
                ),
                ConfigField(
                    key="max_items",
                    type="integer",
                    label="Max Items",
                    description="Maximum items",
                    default=100,
                    required=False,
                ),
            ],
            supports_direct_export=True,
        )
        register_component_settings("export", "multi-field", schema)

        # Check all fields are registered
        assert "export.multi-field.vault_path" in SETTINGS_REGISTRY
        assert "export.multi-field.include_content" in SETTINGS_REGISTRY
        assert "export.multi-field.max_items" in SETTINGS_REGISTRY

    def test_field_types_are_mapped_correctly(self):
        """Test that ConfigField types map to correct Python types."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(key="str_field", type="string", label="", description=""),
                ConfigField(key="bool_field", type="boolean", label="", description=""),
                ConfigField(key="int_field", type="integer", label="", description=""),
                ConfigField(key="path_field", type="path", label="", description=""),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "types-test", schema)

        assert SETTINGS_REGISTRY["export.types-test.str_field"].type is str
        assert SETTINGS_REGISTRY["export.types-test.bool_field"].type is bool
        assert SETTINGS_REGISTRY["export.types-test.int_field"].type is int
        assert SETTINGS_REGISTRY["export.types-test.path_field"].type is str  # Path stored as string

    def test_field_defaults_are_preserved(self):
        """Test that field default values are preserved in settings."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="has_default",
                    type="string",
                    label="",
                    description="",
                    default="my-default-value",
                ),
                ConfigField(
                    key="no_default",
                    type="string",
                    label="",
                    description="",
                    default=None,
                ),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "defaults-test", schema)

        assert SETTINGS_REGISTRY["export.defaults-test.has_default"].default == "my-default-value"
        assert SETTINGS_REGISTRY["export.defaults-test.no_default"].default is None

    def test_field_description_is_preserved(self):
        """Test that field descriptions are preserved in settings."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="described_field",
                    type="string",
                    label="Described",
                    description="This is a detailed description",
                ),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "desc-test", schema)

        assert SETTINGS_REGISTRY["export.desc-test.described_field"].description == "This is a detailed description"

    def test_env_var_generated_from_name_and_key(self):
        """Test that env var names are generated correctly."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="vault_path",
                    type="path",
                    label="",
                    description="",
                ),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "obsidian", schema)

        assert SETTINGS_REGISTRY["export.obsidian.vault_path"].env_var == "OBSIDIAN_VAULT_PATH"

    def test_does_not_override_existing_settings(self):
        """Test that existing settings are not overridden."""
        # First, add a setting manually
        SETTINGS_REGISTRY["export.manual.field"] = SettingDef(
            category="export",
            type=str,
            default="manual-value",
            editable=False,  # Different from auto-registered
            env_var="MANUAL_FIELD",
            description="Manual setting",
        )

        # Now try to auto-register the same key
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="field",
                    type="string",
                    label="",
                    description="Auto description",
                    default="auto-value",
                ),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "manual", schema)

        # Original should be preserved
        setting = SETTINGS_REGISTRY["export.manual.field"]
        assert setting.default == "manual-value"
        assert setting.editable is False
        assert setting.description == "Manual setting"

    def test_works_with_different_component_types(self):
        """Test that different component types use correct prefixes."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(key="api_key", type="string", label="", description=""),
            ],
            supports_direct_export=False,
        )

        register_component_settings("provider", "test-provider", schema)
        register_component_settings("fetch", "test-fetcher", schema)

        # Provider type does NOT get enabled setting (providers are always available if configured)
        assert "provider.test-provider.enabled" not in SETTINGS_REGISTRY
        assert "provider.test-provider.api_key" in SETTINGS_REGISTRY

        # Fetcher type does NOT get enabled setting (fetchers are always active)
        assert "fetch.test-fetcher.enabled" not in SETTINGS_REGISTRY
        assert "fetch.test-fetcher.api_key" in SETTINGS_REGISTRY

    def test_all_fields_are_editable(self):
        """Test that auto-registered fields are always editable."""
        schema = ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="some_field",
                    type="string",
                    label="",
                    description="",
                ),
            ],
            supports_direct_export=False,
        )
        register_component_settings("export", "editable-test", schema)

        assert SETTINGS_REGISTRY["export.editable-test.some_field"].editable is True
        assert SETTINGS_REGISTRY["export.editable-test.enabled"].editable is True

    def test_empty_schema_only_registers_enabled(self):
        """Test that empty schema still registers the enabled setting."""
        schema = ExporterConfigSchema(fields=[], supports_direct_export=False)
        register_component_settings("export", "empty-schema", schema)

        # Only enabled should be registered
        keys_added = [k for k in SETTINGS_REGISTRY.keys() if k.startswith("export.empty-schema.")]
        assert keys_added == ["export.empty-schema.enabled"]
