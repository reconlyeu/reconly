"""YAML sources import utility.

Migrates sources from YAML configuration to the database.
Supports importing sources and optionally creating a feed with them.
"""
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from reconly_core.config.loader import load_config
from reconly_core.database.models import Source, Feed, FeedSource

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of a YAML import operation."""
    sources_created: int = 0
    sources_skipped: int = 0
    sources_failed: int = 0
    feed_created: bool = False
    feed_id: Optional[int] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def total_sources(self) -> int:
        return self.sources_created + self.sources_skipped + self.sources_failed


def import_sources_from_yaml(
    session: Session,
    config_path: Optional[str] = None,
    user_id: Optional[int] = None,
    create_feed: bool = False,
    feed_name: Optional[str] = None,
    skip_existing: bool = True,
    enabled_only: bool = True,
) -> ImportResult:
    """
    Import sources from a YAML configuration file into the database.

    Args:
        session: SQLAlchemy database session
        config_path: Path to sources.yaml (default: config/sources.yaml)
        user_id: Optional user ID to associate with imported sources
        create_feed: Whether to create a feed with all imported sources
        feed_name: Name for the created feed (default: "Imported Feed")
        skip_existing: Skip sources that already exist (by URL)
        enabled_only: Only import enabled sources from YAML

    Returns:
        ImportResult with counts and any errors
    """
    result = ImportResult()

    # Load YAML config
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        result.errors.append(f"Config file not found: {e}")
        return result
    except Exception as e:
        result.errors.append(f"Failed to load config: {e}")
        return result

    # Get sources to import
    sources_to_import = config.enabled_sources if enabled_only else config.sources

    if not sources_to_import:
        result.errors.append("No sources found in config file")
        return result

    logger.info(f"Found {len(sources_to_import)} sources to import")

    # Import each source
    imported_sources: List[Source] = []

    for source_config in sources_to_import:
        try:
            # Check if source already exists (by URL)
            if skip_existing:
                existing = session.query(Source).filter(
                    Source.url == source_config.url
                ).first()

                if existing:
                    logger.debug(f"Skipping existing source: {source_config.name}")
                    result.sources_skipped += 1
                    # Still add to imported list for feed creation
                    imported_sources.append(existing)
                    continue

            # Create new source
            source = Source(
                user_id=user_id,
                name=source_config.name,
                type=source_config.type,
                url=source_config.url,
                config={"tags": source_config.tags} if source_config.tags else None,
                enabled=source_config.enabled,
                default_language=source_config.language,
                default_provider=source_config.provider,
                default_model=source_config.model,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(source)
            session.flush()  # Get the ID

            imported_sources.append(source)
            result.sources_created += 1
            logger.info(f"Created source: {source_config.name} (ID: {source.id})")

        except Exception as e:
            result.sources_failed += 1
            result.errors.append(f"Failed to import '{source_config.name}': {e}")
            logger.error(f"Failed to import source: {e}")

    # Create feed if requested
    if create_feed and imported_sources:
        try:
            feed = Feed(
                user_id=user_id,
                name=feed_name or "Imported Feed",
                description=f"Imported from YAML on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                schedule_enabled=False,  # Don't auto-schedule imported feeds
                output_config={"db": True},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(feed)
            session.flush()  # Get the ID

            # Create feed-source associations
            for idx, source in enumerate(imported_sources):
                feed_source = FeedSource(
                    feed_id=feed.id,
                    source_id=source.id,
                    enabled=True,
                    priority=len(imported_sources) - idx,  # Higher priority for first sources
                )
                session.add(feed_source)

            result.feed_created = True
            result.feed_id = feed.id
            logger.info(f"Created feed '{feed.name}' (ID: {feed.id}) with {len(imported_sources)} sources")

        except Exception as e:
            result.errors.append(f"Failed to create feed: {e}")
            logger.error(f"Failed to create feed: {e}")

    # Commit transaction
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        result.errors.append(f"Failed to commit transaction: {e}")
        logger.error(f"Commit failed: {e}")

    return result


def import_single_source(
    session: Session,
    name: str,
    source_type: str,
    url: str,
    user_id: Optional[int] = None,
    language: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tags: Optional[List[str]] = None,
    enabled: bool = True,
) -> Source:
    """
    Import a single source directly (not from YAML).

    Args:
        session: SQLAlchemy database session
        name: Source name
        source_type: Type (rss, youtube, website, blog)
        url: Source URL
        user_id: Optional user ID
        language: Default language for summaries
        provider: Default LLM provider
        model: Default model name
        tags: Tags for categorization
        enabled: Whether source is enabled

    Returns:
        Created Source entity

    Raises:
        ValueError: If source with URL already exists
    """
    # Check for existing
    existing = session.query(Source).filter(Source.url == url).first()
    if existing:
        raise ValueError(f"Source with URL already exists: {url}")

    source = Source(
        user_id=user_id,
        name=name,
        type=source_type,
        url=url,
        config={"tags": tags} if tags else None,
        enabled=enabled,
        default_language=language,
        default_provider=provider,
        default_model=model,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    session.add(source)
    session.commit()

    return source


def export_sources_to_yaml(
    session: Session,
    output_path: str,
    user_id: Optional[int] = None,
    enabled_only: bool = True,
) -> int:
    """
    Export database sources back to YAML format.

    Args:
        session: SQLAlchemy database session
        output_path: Path for output YAML file
        user_id: Filter by user (None = all sources)
        enabled_only: Only export enabled sources

    Returns:
        Number of sources exported
    """
    import yaml

    # Query sources
    query = session.query(Source)

    if user_id is not None:
        query = query.filter(Source.user_id == user_id)

    if enabled_only:
        query = query.filter(Source.enabled == True)

    sources = query.all()

    # Build YAML structure
    yaml_sources = []
    for source in sources:
        source_dict = {
            "name": source.name,
            "type": source.type,
            "url": source.url,
            "enabled": source.enabled,
        }

        # Add optional fields
        if source.config and source.config.get("tags"):
            source_dict["tags"] = source.config["tags"]

        if source.default_language:
            source_dict["language"] = source.default_language

        if source.default_provider:
            source_dict["provider"] = source.default_provider

        if source.default_model:
            source_dict["model"] = source.default_model

        yaml_sources.append(source_dict)

    # Write YAML file
    output_data = {
        "sources": yaml_sources,
        "settings": {
            "exported_at": datetime.utcnow().isoformat(),
            "total_sources": len(yaml_sources),
        }
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(output_data, f, default_flow_style=False, allow_unicode=True)

    return len(yaml_sources)
