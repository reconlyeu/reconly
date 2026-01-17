#!/usr/bin/env python
"""Load demo seed data into the database.

This script loads demo seed data from JSON fixtures into the database.
It is designed to be run from the Docker demo entrypoint or manually.

Features:
- Loads tags, sources, templates, feeds, and digests in correct dependency order
- Idempotent: skips existing data by name/URL (unless DEMO_RESET=true)
- Supports DEMO_RESET=true to clear and reload demo data
- Uses existing SQLAlchemy models and services
- Transaction-safe with rollback on critical errors

Usage:
    python scripts/load_demo_seed.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    DEMO_RESET: If "true", clear existing demo data before loading
"""
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add packages to path for imports
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "core"))
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "api"))

from reconly_core.logging import configure_logging, get_logger
from reconly_core.database import (
    Base, Tag, Source, Feed, FeedSource, FeedRun, PromptTemplate, ReportTemplate,
    Digest, DigestTag,
    seed_default_templates,
)
from reconly_core.database.models import DigestSourceItem, SourceContent


# Configure logging
configure_logging(log_level="INFO", json_output=False, development=True)
logger = get_logger(__name__)


# Default seed data path (matches Dockerfile COPY destination)
DEFAULT_SEED_PATH = Path("/app/seed")
# Alternative path for local development
DEV_SEED_PATH = _PROJECT_ROOT / "docker" / "demo" / "seed"


def get_seed_path() -> Path:
    """Get the seed data directory path."""
    if DEFAULT_SEED_PATH.exists():
        return DEFAULT_SEED_PATH
    if DEV_SEED_PATH.exists():
        return DEV_SEED_PATH
    raise FileNotFoundError(
        f"Seed data directory not found at {DEFAULT_SEED_PATH} or {DEV_SEED_PATH}"
    )


def load_json_file(path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_database_url() -> str:
    """Get database URL from environment or default."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://reconly:reconly@localhost:5432/reconly"
    )


def create_session() -> Session:
    """Create a database session."""
    database_url = get_database_url()
    engine = create_engine(database_url, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def clear_demo_data(session: Session) -> dict:
    """Clear existing demo data for reset.

    Clears digests, feed_runs, feeds, sources, and tags (in correct order for FK constraints).
    Does NOT clear builtin templates - those are managed by seed_default_templates.

    Returns:
        Dict with counts of deleted items
    """
    result = {
        "digests_deleted": 0,
        "feed_runs_deleted": 0,
        "feeds_deleted": 0,
        "sources_deleted": 0,
        "tags_deleted": 0,
    }

    try:
        # Delete in reverse dependency order:
        # digests -> feed_runs -> feeds -> sources -> tags

        # Delete digests first (has FKs to feed_runs, sources, and tags via DigestTag)
        # DigestSourceItem and SourceContent cascade from Digest
        result["digests_deleted"] = session.query(Digest).delete()

        # Delete feed runs (depends on feeds)
        result["feed_runs_deleted"] = session.query(FeedRun).delete()

        # Delete feeds (depends on sources via FeedSource)
        result["feeds_deleted"] = session.query(Feed).delete()

        # Delete sources (may have FeedSource refs, but those cascade)
        result["sources_deleted"] = session.query(Source).delete()

        # Delete tags
        result["tags_deleted"] = session.query(Tag).delete()

        session.commit()
        logger.info(
            "Cleared existing demo data",
            digests=result["digests_deleted"],
            feed_runs=result["feed_runs_deleted"],
            feeds=result["feeds_deleted"],
            sources=result["sources_deleted"],
            tags=result["tags_deleted"],
        )
    except Exception as e:
        session.rollback()
        logger.error("Failed to clear demo data", error=str(e))
        raise

    return result


def load_tags(session: Session, seed_path: Path) -> dict:
    """Load tags from seed data.

    Args:
        session: Database session
        seed_path: Path to seed data directory

    Returns:
        Dict with counts and name->Tag mapping
    """
    result = {"created": 0, "skipped": 0, "tags": {}}

    tags_file = seed_path / "tags.json"
    if not tags_file.exists():
        logger.warning("Tags seed file not found", path=str(tags_file))
        return result

    data = load_json_file(tags_file)
    tags_data = data.get("tags", [])

    for tag_data in tags_data:
        name = tag_data.get("name")
        if not name:
            continue

        # Check if tag already exists
        existing = session.query(Tag).filter(Tag.name == name).first()
        if existing:
            result["skipped"] += 1
            result["tags"][name] = existing
            continue

        # Create new tag
        tag = Tag(name=name)
        session.add(tag)
        session.flush()  # Get ID
        result["tags"][name] = tag
        result["created"] += 1

    session.commit()
    logger.info(
        "Loaded tags",
        created=result["created"],
        skipped=result["skipped"],
    )
    return result


def load_sources(session: Session, seed_path: Path) -> dict:
    """Load sources from seed data.

    Args:
        session: Database session
        seed_path: Path to seed data directory

    Returns:
        Dict with counts and name->Source mapping
    """
    result = {"created": 0, "skipped": 0, "failed": 0, "sources": {}}

    sources_file = seed_path / "sources.json"
    if not sources_file.exists():
        logger.warning("Sources seed file not found", path=str(sources_file))
        return result

    data = load_json_file(sources_file)
    sources_data = data.get("sources", [])

    for source_data in sources_data:
        name = source_data.get("name")
        if not name:
            continue

        try:
            # Check if source already exists (by name)
            existing = session.query(Source).filter(Source.name == name).first()
            if existing:
                result["skipped"] += 1
                result["sources"][name] = existing
                continue

            # Create new source
            source = Source(
                name=name,
                type=source_data.get("type", "rss"),
                url=source_data.get("url", ""),
                enabled=source_data.get("enabled", True),
                config=source_data.get("config"),
                default_language=source_data.get("default_language"),
                default_provider=source_data.get("default_provider"),
                default_model=source_data.get("default_model"),
                include_keywords=source_data.get("include_keywords"),
                exclude_keywords=source_data.get("exclude_keywords"),
                filter_mode=source_data.get("filter_mode"),
                use_regex=source_data.get("use_regex", False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(source)
            session.flush()  # Get ID
            result["sources"][name] = source
            result["created"] += 1

        except Exception as e:
            result["failed"] += 1
            logger.error("Failed to create source", name=name, error=str(e))

    session.commit()
    logger.info(
        "Loaded sources",
        created=result["created"],
        skipped=result["skipped"],
        failed=result["failed"],
    )
    return result


def load_templates(session: Session, seed_path: Path) -> dict:
    """Load custom templates from seed data.

    Note: Builtin templates are loaded separately via seed_default_templates().
    This function only loads custom demo-specific templates.

    Args:
        session: Database session
        seed_path: Path to seed data directory

    Returns:
        Dict with counts and name->Template mappings
    """
    result = {
        "prompt_created": 0,
        "prompt_skipped": 0,
        "report_created": 0,
        "report_skipped": 0,
        "prompt_templates": {},
        "report_templates": {},
    }

    templates_file = seed_path / "templates.json"
    if not templates_file.exists():
        logger.warning("Templates seed file not found", path=str(templates_file))
        return result

    data = load_json_file(templates_file)

    # Load custom prompt templates
    prompt_templates = data.get("prompt_templates", [])
    for template_data in prompt_templates:
        name = template_data.get("name")
        if not name:
            continue

        existing = session.query(PromptTemplate).filter(
            PromptTemplate.name == name
        ).first()
        if existing:
            result["prompt_skipped"] += 1
            result["prompt_templates"][name] = existing
            continue

        template = PromptTemplate(
            name=name,
            description=template_data.get("description"),
            system_prompt=template_data.get("system_prompt", ""),
            user_prompt_template=template_data.get("user_prompt_template", ""),
            language=template_data.get("language", "en"),
            target_length=template_data.get("target_length", 150),
            model_provider=template_data.get("model_provider"),
            model_name=template_data.get("model_name"),
            origin="user",  # Custom templates are user-created
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(template)
        session.flush()
        result["prompt_templates"][name] = template
        result["prompt_created"] += 1

    # Load custom report templates
    report_templates = data.get("report_templates", [])
    for template_data in report_templates:
        name = template_data.get("name")
        if not name:
            continue

        existing = session.query(ReportTemplate).filter(
            ReportTemplate.name == name
        ).first()
        if existing:
            result["report_skipped"] += 1
            result["report_templates"][name] = existing
            continue

        template = ReportTemplate(
            name=name,
            description=template_data.get("description"),
            format=template_data.get("format", "markdown"),
            template_content=template_data.get("template_content", ""),
            origin="user",  # Custom templates are user-created
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(template)
        session.flush()
        result["report_templates"][name] = template
        result["report_created"] += 1

    session.commit()
    logger.info(
        "Loaded custom templates",
        prompt_created=result["prompt_created"],
        prompt_skipped=result["prompt_skipped"],
        report_created=result["report_created"],
        report_skipped=result["report_skipped"],
    )
    return result


def get_prompt_template_by_name(session: Session, name: str) -> Optional[PromptTemplate]:
    """Get a prompt template by name (checks both builtin and user templates)."""
    return session.query(PromptTemplate).filter(
        PromptTemplate.name == name
    ).first()


def load_feeds(
    session: Session,
    seed_path: Path,
    sources_map: dict[str, Source],
) -> dict:
    """Load feeds from seed data.

    Args:
        session: Database session
        seed_path: Path to seed data directory
        sources_map: Mapping of source names to Source objects

    Returns:
        Dict with counts and name->Feed mapping
    """
    result = {"created": 0, "skipped": 0, "failed": 0, "feeds": {}}

    feeds_file = seed_path / "feeds.json"
    if not feeds_file.exists():
        logger.warning("Feeds seed file not found", path=str(feeds_file))
        return result

    data = load_json_file(feeds_file)
    feeds_data = data.get("feeds", [])

    for feed_data in feeds_data:
        name = feed_data.get("name")
        if not name:
            continue

        try:
            # Check if feed already exists (by name)
            existing = session.query(Feed).filter(Feed.name == name).first()
            if existing:
                result["skipped"] += 1
                result["feeds"][name] = existing
                continue

            # Resolve prompt template by name
            prompt_template_id = None
            prompt_template_name = feed_data.get("prompt_template")
            if prompt_template_name:
                template = get_prompt_template_by_name(session, prompt_template_name)
                if template:
                    prompt_template_id = template.id
                else:
                    logger.warning(
                        "Prompt template not found",
                        feed=name,
                        template=prompt_template_name,
                    )

            # Create feed
            feed = Feed(
                name=name,
                description=feed_data.get("description"),
                digest_mode=feed_data.get("digest_mode", "individual"),
                schedule_cron=feed_data.get("schedule_cron"),
                schedule_enabled=feed_data.get("schedule_enabled", False),
                prompt_template_id=prompt_template_id,
                output_config={"db": True},  # Default: save to database
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(feed)
            session.flush()  # Get ID

            # Create feed-source associations
            source_names = feed_data.get("sources", [])
            for priority, source_name in enumerate(source_names):
                source = sources_map.get(source_name)
                if not source:
                    logger.warning(
                        "Source not found for feed",
                        feed=name,
                        source=source_name,
                    )
                    continue

                feed_source = FeedSource(
                    feed_id=feed.id,
                    source_id=source.id,
                    enabled=True,
                    priority=len(source_names) - priority,  # Higher = first
                )
                session.add(feed_source)

            result["feeds"][name] = feed
            result["created"] += 1
            logger.debug("Created feed", name=name, sources=len(source_names))

        except Exception as e:
            result["failed"] += 1
            logger.error("Failed to create feed", name=name, error=str(e))

    session.commit()
    logger.info(
        "Loaded feeds",
        created=result["created"],
        skipped=result["skipped"],
        failed=result["failed"],
    )
    return result


def create_feed_runs(
    session: Session,
    feeds_map: dict[str, Feed],
) -> dict[str, FeedRun]:
    """Create FeedRun records for each feed.

    Each feed needs a completed FeedRun for digests to link to.
    Returns a mapping of feed_name -> FeedRun.
    """
    feed_runs = {}

    for feed_name, feed in feeds_map.items():
        # Check if a feed run already exists for this feed
        existing = session.query(FeedRun).filter(
            FeedRun.feed_id == feed.id,
            FeedRun.triggered_by == 'demo_seed',
        ).first()

        if existing:
            feed_runs[feed_name] = existing
            continue

        # Count the feed sources for metrics
        source_count = len(feed.feed_sources) if feed.feed_sources else 0

        feed_run = FeedRun(
            feed_id=feed.id,
            triggered_by='demo_seed',
            status='completed',
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            sources_total=source_count,
            sources_processed=source_count,
            sources_failed=0,
            items_processed=0,  # Will be updated after digests are loaded
        )
        session.add(feed_run)
        session.flush()
        feed_runs[feed_name] = feed_run

    session.commit()
    logger.info("Created feed runs", count=len(feed_runs))
    return feed_runs


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        # Handle various ISO formats
        dt_str = dt_str.replace('Z', '+00:00')
        return datetime.fromisoformat(dt_str.replace('+00:00', ''))
    except (ValueError, AttributeError):
        return None


def load_digests(
    session: Session,
    seed_path: Path,
    feeds_map: dict[str, Feed],
    sources_map: dict[str, Source],
    tags_map: dict[str, Tag],
    feed_runs_map: dict[str, FeedRun],
) -> dict:
    """Load digests from seed data.

    Args:
        session: Database session
        seed_path: Path to seed data directory
        feeds_map: Mapping of feed names to Feed objects
        sources_map: Mapping of source names to Source objects
        tags_map: Mapping of tag names to Tag objects
        feed_runs_map: Mapping of feed names to FeedRun objects

    Returns:
        Dict with counts of created/skipped/failed digests
    """
    result = {
        "created": 0,
        "skipped": 0,
        "failed": 0,
        "source_items_created": 0,
        "source_contents_created": 0,
        "tags_linked": 0,
    }

    digests_file = seed_path / "digests.json"
    if not digests_file.exists():
        logger.warning("Digests seed file not found", path=str(digests_file))
        return result

    data = load_json_file(digests_file)
    digests_data = data.get("digests", [])

    # Track items per feed run for updating metrics
    feed_run_item_counts: dict[int, int] = {}

    for digest_data in digests_data:
        url = digest_data.get("url")
        if not url:
            logger.warning("Digest missing URL, skipping")
            continue

        try:
            # Check if digest already exists (by URL - unique constraint)
            existing = session.query(Digest).filter(Digest.url == url).first()
            if existing:
                result["skipped"] += 1
                continue

            # Resolve feed reference
            feed_name = digest_data.get("feed_name")
            feed = feeds_map.get(feed_name) if feed_name else None
            if not feed:
                logger.warning(
                    "Feed not found for digest",
                    url=url[:50],
                    feed_name=feed_name,
                )

            # Resolve source reference
            source_name = digest_data.get("source_name")
            source = sources_map.get(source_name) if source_name else None
            if not source:
                logger.warning(
                    "Source not found for digest",
                    url=url[:50],
                    source_name=source_name,
                )

            # Get feed run for this feed
            feed_run = feed_runs_map.get(feed_name) if feed_name else None

            # Parse published_at
            published_at = parse_datetime(digest_data.get("published_at"))

            # Create digest
            digest = Digest(
                url=url,
                title=digest_data.get("title"),
                content=digest_data.get("content"),
                summary=digest_data.get("summary"),
                source_type=digest_data.get("source_type", "rss"),
                feed_url=digest_data.get("feed_url"),
                feed_title=digest_data.get("feed_title"),
                author=digest_data.get("author"),
                published_at=published_at,
                provider=digest_data.get("provider"),
                language=digest_data.get("language", "en"),
                estimated_cost=0.0,  # Demo data has no cost
                consolidated_count=1,  # Individual digest
                embedding_status=None,  # Will be embedded on first startup
                feed_run_id=feed_run.id if feed_run else None,
                source_id=source.id if source else None,
                created_at=datetime.utcnow(),
            )
            session.add(digest)
            session.flush()  # Get ID

            # Track item count for feed run
            if feed_run:
                feed_run_item_counts[feed_run.id] = feed_run_item_counts.get(feed_run.id, 0) + 1

            # Link tags
            tag_names = digest_data.get("tags", [])
            for tag_name in tag_names:
                tag = tags_map.get(tag_name)
                if tag:
                    digest_tag = DigestTag(
                        digest_id=digest.id,
                        tag_id=tag.id,
                    )
                    session.add(digest_tag)
                    result["tags_linked"] += 1
                else:
                    logger.debug("Tag not found", tag_name=tag_name)

            # Create DigestSourceItem for provenance
            if source:
                source_item = DigestSourceItem(
                    digest_id=digest.id,
                    source_id=source.id,
                    item_url=url,
                    item_title=digest_data.get("title"),
                    item_published_at=published_at,
                    created_at=datetime.utcnow(),
                )
                session.add(source_item)
                session.flush()  # Get ID for SourceContent
                result["source_items_created"] += 1

                # Create SourceContent for RAG embedding
                content = digest_data.get("content", "")
                if content:
                    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                    source_content = SourceContent(
                        digest_source_item_id=source_item.id,
                        content=content,
                        content_hash=content_hash,
                        content_length=len(content),
                        fetched_at=datetime.utcnow(),
                        embedding_status=None,  # Will be embedded on first startup
                        created_at=datetime.utcnow(),
                    )
                    session.add(source_content)
                    result["source_contents_created"] += 1

            result["created"] += 1
            logger.debug("Created digest", title=digest_data.get("title", "")[:50])

        except Exception as e:
            result["failed"] += 1
            logger.error(
                "Failed to create digest",
                url=url[:50] if url else "unknown",
                error=str(e),
            )

    # Update feed run item counts
    for feed_run_id, item_count in feed_run_item_counts.items():
        feed_run = session.query(FeedRun).filter(FeedRun.id == feed_run_id).first()
        if feed_run:
            feed_run.items_processed = item_count

    session.commit()
    logger.info(
        "Loaded digests",
        created=result["created"],
        skipped=result["skipped"],
        failed=result["failed"],
        source_items=result["source_items_created"],
        source_contents=result["source_contents_created"],
        tags_linked=result["tags_linked"],
    )
    return result


def load_demo_seed() -> dict:
    """Main function to load all demo seed data.

    Returns:
        Dict with summary of all loaded data
    """
    logger.info("Starting demo seed data load")

    # Check for reset flag
    demo_reset = os.getenv("DEMO_RESET", "false").lower() == "true"
    if demo_reset:
        logger.info("DEMO_RESET=true - will clear existing data")

    # Get seed path
    try:
        seed_path = get_seed_path()
        logger.info("Using seed data path", path=str(seed_path))
    except FileNotFoundError as e:
        logger.error("Seed data directory not found", error=str(e))
        return {"success": False, "error": str(e)}

    # Create database session
    session = create_session()

    try:
        # Clear existing data if reset requested
        if demo_reset:
            clear_demo_data(session)

        # Load builtin templates first (from seed.py)
        logger.info("Seeding builtin templates")
        builtin_result = seed_default_templates(session, force=demo_reset)
        logger.info(
            "Builtin templates seeded",
            prompt_created=builtin_result["prompt_templates_created"],
            report_created=builtin_result["report_templates_created"],
        )

        # Load data in dependency order:
        # tags -> templates -> sources -> feeds -> feed_runs -> digests
        tags_result = load_tags(session, seed_path)
        sources_result = load_sources(session, seed_path)
        templates_result = load_templates(session, seed_path)
        feeds_result = load_feeds(
            session,
            seed_path,
            sources_result["sources"],
        )

        # Create feed runs (required for digests to link to)
        feed_runs_map = create_feed_runs(session, feeds_result["feeds"])

        # Load digests with all references resolved
        digests_result = load_digests(
            session,
            seed_path,
            feeds_result["feeds"],
            sources_result["sources"],
            tags_result["tags"],
            feed_runs_map,
        )

        # Summary
        summary = {
            "success": True,
            "reset": demo_reset,
            "builtin_templates": builtin_result,
            "tags": {
                "created": tags_result["created"],
                "skipped": tags_result["skipped"],
            },
            "sources": {
                "created": sources_result["created"],
                "skipped": sources_result["skipped"],
                "failed": sources_result["failed"],
            },
            "custom_templates": {
                "prompt_created": templates_result["prompt_created"],
                "report_created": templates_result["report_created"],
            },
            "feeds": {
                "created": feeds_result["created"],
                "skipped": feeds_result["skipped"],
                "failed": feeds_result["failed"],
            },
            "feed_runs": {
                "created": len(feed_runs_map),
            },
            "digests": {
                "created": digests_result["created"],
                "skipped": digests_result["skipped"],
                "failed": digests_result["failed"],
                "source_items": digests_result["source_items_created"],
                "source_contents": digests_result["source_contents_created"],
                "tags_linked": digests_result["tags_linked"],
            },
        }

        logger.info("Demo seed data load complete", **summary)
        return summary

    except Exception as e:
        session.rollback()
        logger.error("Failed to load demo seed data", error=str(e), exc_info=True)
        return {"success": False, "error": str(e)}

    finally:
        session.close()


if __name__ == "__main__":
    result = load_demo_seed()
    if result.get("success"):
        print("\n" + "=" * 50)
        print("Demo seed data loaded successfully!")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("Failed to load demo seed data!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        print("=" * 50)
        sys.exit(1)
