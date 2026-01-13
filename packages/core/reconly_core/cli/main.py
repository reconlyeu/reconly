#!/usr/bin/env python3
"""Daily Digest - Main CLI script for fetching and summarizing content."""
import argparse
import sys
from typing import List, Optional
from dotenv import load_dotenv

from reconly_core.cli.commands import CommandHandler


def parse_tags(tags_str: Optional[str]) -> Optional[List[str]]:
    """
    Parse comma-separated tags string.

    Args:
        tags_str: Comma-separated tags

    Returns:
        List of tags or None
    """
    if not tags_str:
        return None
    return [t.strip() for t in tags_str.split(',')]


def main():
    """Main entry point."""
    # Fix Windows console encoding for Unicode (emoji) output
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python < 3.7 fallback
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description='Daily Digest - Fetch and summarize content from websites, YouTube videos, and RSS feeds'
    )

    # Mutually exclusive group for different modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('url', nargs='?', help='URL to fetch and summarize (website, YouTube video, or RSS feed)')
    mode_group.add_argument('--batch', action='store_true', help='Process all sources from config file (legacy YAML mode)')
    mode_group.add_argument('--search', metavar='QUERY', help='Search in saved digests')
    mode_group.add_argument('--list', action='store_true', help='List recent digests')
    mode_group.add_argument('--stats', action='store_true', help='Show database statistics')
    mode_group.add_argument('--export', metavar='FILE', help='Export digests to JSON or CSV file')
    mode_group.add_argument('--send-digest', action='store_true', help='Send recent digests via email')
    # New database-driven commands
    mode_group.add_argument('--init', action='store_true', help='Initialize database with schema and default templates')
    mode_group.add_argument('--import', dest='import_sources', action='store_true', help='Import sources from YAML config to database')
    mode_group.add_argument('--sources', action='store_true', help='List all sources in database')
    mode_group.add_argument('--feeds', action='store_true', help='List all feeds in database')
    mode_group.add_argument('--run-feed', metavar='FEED_ID', type=int, help='Run a specific feed by ID')
    # RAG embedding commands
    mode_group.add_argument('--embed-all', action='store_true', help='Backfill embeddings for all unembedded digests')
    mode_group.add_argument('--embed-stats', action='store_true', help='Show embedding statistics')

    # Summarization options
    parser.add_argument(
        '-l', '--language',
        default='de',
        choices=['de', 'en'],
        help='Summary language (default: de)'
    )
    parser.add_argument(
        '--provider',
        choices=['huggingface', 'anthropic'],
        help='LLM provider to use (default: from env or huggingface)'
    )
    parser.add_argument(
        '--model',
        help='Model to use (for HuggingFace: glm-4, mixtral, llama, mistral)'
    )
    parser.add_argument(
        '--api-key',
        help='API key for the selected provider'
    )
    parser.add_argument(
        '--no-fallback',
        action='store_true',
        help='Disable automatic fallback to other providers'
    )
    parser.add_argument(
        '--show-cost',
        action='store_true',
        help='Show estimated costs for API calls'
    )

    # Database options
    parser.add_argument(
        '--save',
        action='store_true',
        help='Save digest to database'
    )
    parser.add_argument(
        '--tags',
        help='Comma-separated tags for this digest'
    )
    parser.add_argument(
        '--db-url',
        help='Database URL (default: from env or postgresql://localhost/reconly)'
    )

    # RSS/Feed options
    parser.add_argument(
        '--reset-tracking',
        action='store_true',
        help='Reset tracking for this feed (process all articles again)'
    )

    # Search/List/Export options
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Limit results (default: 10)'
    )
    parser.add_argument(
        '--source-type',
        choices=['website', 'youtube', 'rss'],
        help='Filter by source type'
    )
    parser.add_argument(
        '--config',
        help='Path to config file (default: config/sources.yaml)'
    )

    # Email options
    parser.add_argument(
        '--email',
        help='Email address to send digest to (default: from EMAIL_RECIPIENT env var)'
    )
    parser.add_argument(
        '--email-language',
        choices=['de', 'en'],
        help='Language for email template (default: same as --language)'
    )

    # Import options
    parser.add_argument(
        '--create-feed',
        action='store_true',
        help='When importing, also create a feed with all imported sources'
    )
    parser.add_argument(
        '--feed-name',
        help='Name for the feed created during import (default: "Imported Feed")'
    )
    parser.add_argument(
        '--all-sources',
        action='store_true',
        help='Import all sources including disabled ones'
    )

    # Embedding options
    parser.add_argument(
        '--embed-limit',
        type=int,
        help='Maximum number of digests to embed (for --embed-all)'
    )
    parser.add_argument(
        '--embed-retry-failed',
        action='store_true',
        help='Also retry previously failed embeddings (for --embed-all)'
    )

    args = parser.parse_args()

    # Load environment variables from .env file if it exists
    load_dotenv()

    try:
        # Parse tags if provided
        tags = parse_tags(args.tags)

        # Initialize command handler
        handler = CommandHandler(database_url=args.db_url)

        # Route to appropriate command handler
        if args.search:
            return handler.handle_search(
                query=args.search,
                tags=tags,
                source_type=args.source_type,
                limit=args.limit
            )

        elif args.list:
            return handler.handle_list(
                tags=tags,
                source_type=args.source_type,
                limit=args.limit
            )

        elif args.stats:
            return handler.handle_stats()

        elif args.export:
            return handler.handle_export(
                filename=args.export,
                tags=tags,
                source_type=args.source_type,
                limit=args.limit
            )

        elif args.send_digest:
            email_lang = args.email_language or args.language
            return handler.handle_send_digest(
                to_email=args.email,
                tags=tags,
                source_type=args.source_type,
                limit=args.limit,
                language=email_lang
            )

        elif args.batch:
            return handler.handle_batch(
                config_path=args.config,
                tags=tags,
                source_type=args.source_type,
                language=args.language,
                provider=args.provider,
                model=args.model,
                api_key=args.api_key,
                enable_fallback=not args.no_fallback,
                save=args.save
            )

        # New database-driven commands
        elif args.init:
            return handler.handle_init(seed_templates=True)

        elif args.import_sources:
            return handler.handle_import(
                config_path=args.config,
                create_feed=args.create_feed,
                feed_name=args.feed_name,
                enabled_only=not args.all_sources
            )

        elif args.sources:
            return handler.handle_sources_list()

        elif args.feeds:
            return handler.handle_feeds_list()

        elif args.run_feed:
            return handler.handle_run_feed(
                feed_id=args.run_feed,
                api_key=args.api_key,
                enable_fallback=not args.no_fallback
            )

        # RAG embedding commands
        elif args.embed_all:
            return handler.handle_embed_all(
                limit=args.embed_limit,
                include_failed=args.embed_retry_failed
            )

        elif args.embed_stats:
            return handler.handle_embed_stats()

        # Normal URL processing mode
        elif args.url:
            return handler.handle_url(
                url=args.url,
                language=args.language,
                provider=args.provider,
                model=args.model,
                api_key=args.api_key,
                enable_fallback=not args.no_fallback,
                show_cost=args.show_cost,
                save=args.save,
                tags=tags,
                reset_tracking=args.reset_tracking
            )

        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
