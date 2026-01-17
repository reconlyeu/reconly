#!/usr/bin/env python
"""Load demo seed data into the database.

This script loads demo seed data from JSON fixtures into the database.
It is designed to be run from the Docker demo entrypoint or manually.

Features:
- Loads tags, sources, templates, and feeds in correct dependency order
- Idempotent: skips existing data by name (unless DEMO_RESET=true)
- Supports DEMO_RESET=true to clear and reload demo data
- Uses existing SQLAlchemy models and services
- Transaction-safe with rollback on critical errors

Usage:
    python scripts/load_demo_seed.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    DEMO_RESET: If "true", clear existing demo data before loading
"""
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
    Base, Tag, Source, Feed, FeedSource, PromptTemplate, ReportTemplate,
    seed_default_templates,
)


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

    Clears feeds, sources, and tags (in correct order for FK constraints).
    Does NOT clear builtin templates - those are managed by seed_default_templates.

    Returns:
        Dict with counts of deleted items
    """
    result = {
        "feeds_deleted": 0,
        "sources_deleted": 0,
        "tags_deleted": 0,
    }

    try:
        # Delete feeds first (depends on sources via FeedSource)
        result["feeds_deleted"] = session.query(Feed).delete()

        # Delete sources (may have FeedSource refs, but those cascade)
        result["sources_deleted"] = session.query(Source).delete()

        # Delete tags (digests may ref them, but DigestTag cascades)
        result["tags_deleted"] = session.query(Tag).delete()

        session.commit()
        logger.info(
            "Cleared existing demo data",
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
        Dict with counts of created/skipped feeds
    """
    result = {"created": 0, "skipped": 0, "failed": 0}

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

        # Load data in dependency order
        tags_result = load_tags(session, seed_path)
        sources_result = load_sources(session, seed_path)
        templates_result = load_templates(session, seed_path)
        feeds_result = load_feeds(
            session,
            seed_path,
            sources_result["sources"],
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
