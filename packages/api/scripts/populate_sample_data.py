#!/usr/bin/env python
"""Populate database with sample data for LOCAL DEVELOPMENT ONLY.

WARNING: This script is intended for developer convenience during local development.
It is NOT intended for production deployment or Docker images.

Purpose:
    - Creates a default dev user (dev@example.com)
    - Seeds default prompt/report templates
    - Imports sample feed bundles from the sample_bundles/ directory

Usage:
    cd packages/api
    python scripts/populate_sample_data.py

Note:
    Production/Docker deployments use a separate seed mechanism (load_demo_seed.py)
    with curated demo data. This script and sample_bundles/ are excluded from
    production builds.

Sample feeds are loaded from JSON bundle files in the sample_bundles/ directory.
To add new sample feeds, simply drop a valid bundle JSON file into that folder.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add parent directory to path so we can import reconly_api
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from reconly_api.config import settings
from reconly_core.database.models import User
from reconly_core.database.crud import DigestDB
from reconly_core.database.seed import seed_default_templates
from reconly_core.marketplace.importer import FeedBundleImporter

# Directory containing sample bundle JSON files
SAMPLE_BUNDLES_DIR = Path(__file__).parent / "sample_bundles"


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


def import_sample_bundles(session: Session, user: User) -> dict:
    """Import all sample bundles from the sample_bundles directory.

    Args:
        session: Database session
        user: User to associate with imported feeds

    Returns:
        Dictionary with import statistics
    """
    stats = {
        "imported": [],
        "skipped": [],
        "failed": [],
    }

    if not SAMPLE_BUNDLES_DIR.exists():
        print(f"[WARN] Sample bundles directory not found: {SAMPLE_BUNDLES_DIR}")
        return stats

    bundle_files = sorted(SAMPLE_BUNDLES_DIR.glob("*.json"))
    if not bundle_files:
        print(f"[WARN] No bundle files found in {SAMPLE_BUNDLES_DIR}")
        return stats

    importer = FeedBundleImporter(session)

    for bundle_file in bundle_files:
        try:
            data = json.loads(bundle_file.read_text(encoding="utf-8"))
            result = importer.import_bundle(data, user_id=user.id)

            if result.success:
                print(f"[OK] Imported: {result.feed_name} ({result.sources_created} sources)")
                stats["imported"].append({
                    "file": bundle_file.name,
                    "feed_name": result.feed_name,
                    "feed_id": result.feed_id,
                    "sources": result.sources_created,
                })
                for warning in result.warnings:
                    print(f"     [WARN] {warning}")
            else:
                # Check if it's a duplicate (already exists)
                if any("already exists" in err for err in result.errors):
                    print(f"[SKIP] {bundle_file.name}: Feed already exists")
                    stats["skipped"].append({
                        "file": bundle_file.name,
                        "reason": result.errors[0] if result.errors else "Unknown",
                    })
                else:
                    print(f"[FAIL] {bundle_file.name}: {result.errors}")
                    stats["failed"].append({
                        "file": bundle_file.name,
                        "errors": result.errors,
                    })
        except json.JSONDecodeError as e:
            print(f"[FAIL] {bundle_file.name}: Invalid JSON - {e}")
            stats["failed"].append({
                "file": bundle_file.name,
                "errors": [f"Invalid JSON: {e}"],
            })
        except Exception as e:
            print(f"[FAIL] {bundle_file.name}: {e}")
            stats["failed"].append({
                "file": bundle_file.name,
                "errors": [str(e)],
            })

    return stats


def main():
    """Main function to populate sample data."""
    print("=" * 70)
    print("POPULATING SAMPLE DATA (LOCAL DEVELOPMENT ONLY)")
    print("=" * 70)
    print()
    print("NOTE: Production/Docker uses load_demo_seed.py instead.")
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

        # 3. Import sample bundles
        print(f"3. Importing sample bundles from {SAMPLE_BUNDLES_DIR.name}/...")
        bundle_stats = import_sample_bundles(session, user)
        print()

        print("=" * 70)
        print("[SUCCESS] SAMPLE DATA POPULATION COMPLETE")
        print("=" * 70)
        print()
        print(f"User:      {user.email}")
        print(f"Templates: {result['prompt_templates_created'] + result['prompt_templates_skipped']} prompt, "
              f"{result['report_templates_created'] + result['report_templates_skipped']} report")
        print(f"Bundles:   {len(bundle_stats['imported'])} imported, "
              f"{len(bundle_stats['skipped'])} skipped, "
              f"{len(bundle_stats['failed'])} failed")

        if bundle_stats['imported']:
            print()
            print("Imported feeds:")
            for item in bundle_stats['imported']:
                print(f"  - {item['feed_name']} ({item['sources']} sources)")

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
