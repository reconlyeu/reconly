"""Services package exports."""
from reconly_core.services.digest_service import (
    DigestService,
    ProcessOptions,
    DigestResult,
)
from reconly_core.services.batch_service import (
    BatchService,
    BatchOptions,
    BatchResult,
)
from reconly_core.services.feed_service import (
    FeedService,
    FeedRunOptions,
    FeedRunResult,
)
from reconly_core.services.email_service import EmailService
from reconly_core.services.settings_service import SettingsService
from reconly_core.services.settings_registry import (
    SETTINGS_REGISTRY,
    SettingDef,
    get_settings_by_category,
    get_all_categories,
)
from reconly_core.services.content_filter import ContentFilter

__all__ = [
    # Digest service (legacy, single URL processing)
    'DigestService',
    'ProcessOptions',
    'DigestResult',
    # Batch service (legacy, YAML-based)
    'BatchService',
    'BatchOptions',
    'BatchResult',
    # Feed service (new, DB-based)
    'FeedService',
    'FeedRunOptions',
    'FeedRunResult',
    # Email service
    'EmailService',
    # Settings service
    'SettingsService',
    'SETTINGS_REGISTRY',
    'SettingDef',
    'get_settings_by_category',
    'get_all_categories',
    # Content filter
    'ContentFilter',
]
