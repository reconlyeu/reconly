#!/usr/bin/env python3
"""Clear all test data from the database.

Deletes: feeds, sources, digests, feed_runs, agent_runs, tags, llm_usage_logs.
Preserves: templates (prompt/report), app_settings, users.

Usage:
    cd reconly && python scripts/clear_test_data.py
"""
import os
from sqlalchemy import create_engine, text

# Default database URL - consistent with reconly_core
DEFAULT_DATABASE_URL = 'postgresql://reconly:reconly@localhost:5432/reconly'

def clear_test_data():
    """Clear all test data from the database."""
    database_url = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)
    engine = create_engine(database_url)

    # Tables to clear in order (respecting foreign keys)
    # CASCADE handles most relationships, but we clear in dependency order for safety
    tables_to_clear = [
        # RAG knowledge system (no FKs pointing to them)
        "digest_relationships",
        "digest_chunks",
        "source_content_chunks",
        "source_contents",

        # Junction tables
        "digest_source_items",
        "digest_tags",
        "feed_sources",

        # Usage logs
        "llm_usage_logs",

        # Agent runs
        "agent_runs",

        # Main entities (order matters due to FKs)
        "digests",
        "feed_runs",
        "oauth_credentials",
        "feeds",
        "sources",

        # Tags (orphaned after digest_tags cleared)
        "tags",
    ]

    with engine.connect() as conn:
        print("Clearing test data...\n")

        for table in tables_to_clear:
            try:
                result = conn.execute(text(f"DELETE FROM {table}"))
                count = result.rowcount
                if count > 0:
                    print(f"  [OK] {table}: deleted {count} rows")
                else:
                    print(f"  [--] {table}: empty")
            except Exception as e:
                print(f"  [ERR] {table}: {e}")

        conn.commit()
        print("\nDone! All test data cleared.")

if __name__ == "__main__":
    clear_test_data()
