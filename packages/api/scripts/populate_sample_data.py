#!/usr/bin/env python
"""Populate database with sample data for testing."""
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add parent directory to path so we can import reconly_api
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from reconly_api.config import settings
from reconly_core.database.models import (
    User, Source, Feed, FeedSource, PromptTemplate, ReportTemplate
)
from reconly_core.database.crud import DigestDB
from reconly_core.database.seed import seed_default_templates


def create_default_user(session: Session) -> User:
    """Create or get the default development user."""
    user = session.query(User).filter(User.email == "dev@example.com").first()

    if user:
        print(f"[OK] Default user already exists: {user.email}")
        return user

    user = User(
        email="dev@example.com",
        name="Dev User",
        hashed_password="not-a-real-password-hash",  # This is just for dev
        is_active=True,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    print(f"[OK] Created default user: {user.email}")
    return user


def create_sample_sources(session: Session, user: User) -> list[Source]:
    """Create sample sources for testing."""
    sample_sources = [
        {
            "name": "Hacker News",
            "type": "rss",
            "url": "https://news.ycombinator.com/rss",
            "config": {"max_items": 20},
            "enabled": True,
        },
        {
            "name": "TechCrunch",
            "type": "rss",
            "url": "https://techcrunch.com/feed/",
            "config": {"max_items": 15},
            "enabled": True,
        },
        {
            "name": "Fireship YouTube",
            "type": "youtube",
            "url": "https://www.youtube.com/@Fireship",
            "config": {"max_items": 5},
            "enabled": True,
        },
        {
            "name": "Paul Graham's Blog",
            "type": "blog",
            "url": "http://www.paulgraham.com/articles.html",
            "config": {"fetch_full_content": True},
            "enabled": False,  # Disabled by default
        },
    ]

    created_sources = []
    for source_data in sample_sources:
        # Check if source already exists
        existing = session.query(Source).filter(
            Source.url == source_data["url"]
        ).first()

        if existing:
            print(f"[SKIP] Source already exists: {source_data['name']}")
            created_sources.append(existing)
            continue

        source = Source(
            user_id=user.id,
            name=source_data["name"],
            type=source_data["type"],
            url=source_data["url"],
            config=source_data.get("config"),
            enabled=source_data.get("enabled", True),
            created_at=datetime.now(UTC),
        )
        session.add(source)
        created_sources.append(source)
        print(f"[OK] Created source: {source_data['name']} ({source_data['type']})")

    session.commit()
    return created_sources


def create_sample_feed(session: Session, user: User, sources: list[Source]) -> Feed:
    """Create a sample feed using the created sources."""
    # Check if feed already exists
    existing = session.query(Feed).filter(
        Feed.name == "Tech Daily Digest"
    ).first()

    if existing:
        print(f"[SKIP] Feed already exists: {existing.name}")
        return existing

    # Get default templates
    prompt_template = session.query(PromptTemplate).filter(
        PromptTemplate.name == "Standard Summary (English)",
        PromptTemplate.is_system == True,
    ).first()

    report_template = session.query(ReportTemplate).filter(
        ReportTemplate.name == "Daily Digest (Markdown)",
        ReportTemplate.is_system == True,
    ).first()

    feed = Feed(
        user_id=user.id,
        name="Tech Daily Digest",
        description="Daily digest of tech news from Hacker News and TechCrunch",
        schedule_cron="0 8 * * *",  # Every day at 8 AM
        schedule_enabled=True,
        prompt_template_id=prompt_template.id if prompt_template else None,
        report_template_id=report_template.id if report_template else None,
        output_config={
            "email": {
                "enabled": False,  # Disabled by default
                "recipients": ["dev@example.com"],
            },
            "file": {
                "enabled": True,
                "path": "./output/digests",
            },
        },
        created_at=datetime.now(UTC),
    )
    session.add(feed)
    session.commit()

    # Associate enabled sources with the feed
    enabled_sources = [s for s in sources if s.enabled]
    for priority, source in enumerate(enabled_sources):
        feed_source = FeedSource(
            feed_id=feed.id,
            source_id=source.id,
            enabled=True,
            priority=priority,
        )
        session.add(feed_source)

    session.commit()
    print(f"[OK] Created feed: {feed.name} with {len(enabled_sources)} sources")
    return feed


def main():
    """Main function to populate sample data."""
    print("=" * 70)
    print("POPULATING SAMPLE DATA")
    print("=" * 70)
    print()

    # Get database session via DigestDB
    db = DigestDB(database_url=settings.database_url)
    session = db.session

    try:
        # 1. Seed default templates
        print("1. Seeding default templates...")
        result = seed_default_templates(session)
        print(f"   [OK] Created {result['prompt_templates_created']} prompt templates")
        print(f"   [OK] Created {result['report_templates_created']} report templates")
        if result['prompt_templates_skipped'] > 0:
            print(f"   [SKIP] Skipped {result['prompt_templates_skipped']} existing prompt templates")
        if result['report_templates_skipped'] > 0:
            print(f"   [SKIP] Skipped {result['report_templates_skipped']} existing report templates")
        print()

        # 2. Create default user
        print("2. Creating default user...")
        user = create_default_user(session)
        print()

        # 3. Create sample sources
        print("3. Creating sample sources...")
        sources = create_sample_sources(session, user)
        print()

        # 4. Create sample feed
        print("4. Creating sample feed...")
        feed = create_sample_feed(session, user, sources)
        print()

        print("=" * 70)
        print("[SUCCESS] SAMPLE DATA POPULATION COMPLETE")
        print("=" * 70)
        print()
        print(f"User:     {user.email}")
        print(f"Sources:  {len(sources)} created")
        print(f"Feed:     {feed.name}")
        print(f"Templates: {result['prompt_templates_created'] + result['prompt_templates_skipped']} prompt, "
              f"{result['report_templates_created'] + result['report_templates_skipped']} report")
        print()
        print("You can now start the API server:")
        print("  cd packages/api")
        print("  python -m uvicorn reconly_api.main:app --reload --host 0.0.0.0 --port 8000")
        print()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return 1
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
