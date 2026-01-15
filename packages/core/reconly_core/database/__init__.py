"""Database package exports."""
from reconly_core.database.crud import DigestDB
from reconly_core.database.models import (
    Base,
    User,
    Source,
    Feed,
    FeedSource,
    PromptTemplate,
    ReportTemplate,
    FeedRun,
    AgentRun,
    LLMUsageLog,
    Digest,
    Tag,
    DigestTag,
    OAuthCredential,
    TemplateOrigin,
    EmbeddingStatus,
)
from reconly_core.database.seed import (
    seed_default_templates,
    get_default_prompt_template,
    get_default_report_template,
)
from reconly_core.database.import_sources import (
    import_sources_from_yaml,
    import_single_source,
    export_sources_to_yaml,
    ImportResult,
)

__all__ = [
    # Base
    'Base',
    # Core entities
    'User',
    'Source',
    'Feed',
    'FeedSource',
    'PromptTemplate',
    'ReportTemplate',
    'FeedRun',
    'AgentRun',
    'LLMUsageLog',
    'OAuthCredential',
    # Existing entities
    'Digest',
    'Tag',
    'DigestTag',
    # Types
    'TemplateOrigin',
    'EmbeddingStatus',
    # CRUD
    'DigestDB',
    # Seeding
    'seed_default_templates',
    'get_default_prompt_template',
    'get_default_report_template',
    # Import/Export
    'import_sources_from_yaml',
    'import_single_source',
    'export_sources_to_yaml',
    'ImportResult',
]
