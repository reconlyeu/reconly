"""SQLAlchemy ORM models."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models so Alembic can detect them
from reconly_api.models.user import User
from reconly_api.models.source import Source
from reconly_api.models.template import PromptTemplate, ReportTemplate
from reconly_api.models.feed import Feed, FeedSource
from reconly_api.models.feed_run import FeedRun
from reconly_api.models.digest import Digest, Tag, DigestTag
from reconly_api.models.llm_usage import LLMUsageLog

__all__ = [
    "Base",
    "User",
    "Source",
    "PromptTemplate",
    "ReportTemplate",
    "Feed",
    "FeedSource",
    "FeedRun",
    "Digest",
    "Tag",
    "DigestTag",
    "LLMUsageLog",
]
