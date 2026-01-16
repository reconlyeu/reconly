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
    # RAG knowledge graph commands
    mode_group.add_argument('--rag-rebuild-graph', action='store_true', help='Rebuild knowledge graph from source content')
    mode_group.add_argument('--rag-backfill-source-content', action='store_true', help='Backfill source content for historical digests')
    mode_group.add_argument('--rag-embed-source-content', action='store_true', help='Embed unembedded source content')
    mode_group.add_argument('--rag-graph-stats', action='store_true', help='Show knowledge graph statistics')
    mode_group.add_argument('--rag-source-content-stats', action='store_true', help='Show source content statistics')
    mode_group.add_argument('--rag-prune', action='store_true', help='Prune low-quality graph relationships')

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

    # RAG graph rebuild options
    parser.add_argument(
        '--chunk-source',
        choices=['source_content', 'digest'],
        default='source_content',
        help='Chunk source for semantic similarity (default: source_content)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Batch size for processing (default: 50)'
    )
    parser.add_argument(
        '--clear-existing',
        action='store_true',
        help='Clear existing relationships before rebuilding (for --rag-rebuild-graph)'
    )
    parser.add_argument(
        '--no-tag-relationships',
        action='store_true',
        help='Skip tag-based relationships (for --rag-rebuild-graph)'
    )
    parser.add_argument(
        '--no-source-relationships',
        action='store_true',
        help='Skip source-based relationships (for --rag-rebuild-graph)'
    )

    # RAG backfill options
    parser.add_argument(
        '--refetch',
        action='store_true',
        help='Attempt to re-fetch content from original URLs (for --rag-backfill-source-content)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    # RAG prune options
    parser.add_argument(
        '--prune-min-score',
        type=float,
        help='Remove relationships below this score (for --rag-prune)'
    )
    parser.add_argument(
        '--prune-max-age',
        type=int,
        help='Remove relationships older than this many days (for --rag-prune)'
    )
    parser.add_argument(
        '--prune-max-edges',
        type=int,
        help='Keep only top N edges per digest (for --rag-prune)'
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

        # RAG knowledge graph commands
        elif args.rag_rebuild_graph:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_rebuild_graph(
                chunk_source=args.chunk_source,
                limit=args.limit if args.limit != 10 else None,  # 10 is the default
                batch_size=args.batch_size,
                clear_existing=args.clear_existing,
                include_tag_relationships=not args.no_tag_relationships,
                include_source_relationships=not args.no_source_relationships,
            )

        elif args.rag_backfill_source_content:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_backfill_source_content(
                limit=args.limit if args.limit != 10 else None,
                dry_run=args.dry_run,
                refetch=args.refetch,
            )

        elif args.rag_embed_source_content:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_embed_source_content(
                limit=args.embed_limit,
                include_failed=args.embed_retry_failed,
            )

        elif args.rag_graph_stats:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_graph_stats()

        elif args.rag_source_content_stats:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_source_content_stats()

        elif args.rag_prune:
            from reconly_core.cli.rag_commands import RAGCommandHandler
            rag_handler = RAGCommandHandler(database_url=args.db_url)
            return rag_handler.handle_prune_relationships(
                min_score=args.prune_min_score,
                max_age_days=args.prune_max_age,
                max_edges_per_digest=args.prune_max_edges,
                dry_run=args.dry_run,
            )

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
