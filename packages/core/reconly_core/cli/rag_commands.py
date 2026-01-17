"""RAG (Retrieval-Augmented Generation) CLI commands.

Provides management commands for:
- Rebuilding the knowledge graph from source content
- Backfilling source content for historical digests
- RAG system statistics and maintenance
"""
import asyncio
import logging
from typing import Optional

from reconly_core.database.crud import DigestDB
from reconly_core.rag.search.vector import ChunkSource

logger = logging.getLogger(__name__)


class RAGCommandHandler:
    """Handles RAG-related CLI commands."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize RAG command handler.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url

    def handle_rebuild_graph(
        self,
        chunk_source: ChunkSource = 'source_content',
        limit: Optional[int] = None,
        batch_size: int = 50,
        clear_existing: bool = False,
        include_tag_relationships: bool = True,
        include_source_relationships: bool = True,
    ) -> int:
        """
        Rebuild the knowledge graph from source content embeddings.

        Recomputes all DigestRelationship records using the specified chunk source
        for semantic relationships.

        Args:
            chunk_source: Which chunks to use for semantic similarity
                          ('source_content' or 'digest'). Default: 'source_content'
            limit: Maximum number of digests to process (None = all)
            batch_size: Number of digests to process per batch
            clear_existing: If True, clear all existing relationships first
            include_tag_relationships: Include tag-based relationships
            include_source_relationships: Include source-based relationships

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.database.models import Digest, DigestRelationship
            from reconly_core.rag import GraphService, get_embedding_provider

            print("Rebuilding knowledge graph...")
            print(f"   Chunk source: {chunk_source}")
            if limit:
                print(f"   Limit: {limit} digests")
            print(f"   Batch size: {batch_size}")

            db = DigestDB(database_url=self.database_url)

            # Clear existing relationships if requested
            if clear_existing:
                print("\n   Clearing existing relationships...")
                deleted = db.session.query(DigestRelationship).delete()
                db.session.commit()
                print(f"   Deleted {deleted} existing relationships")

            # Get digests to process
            query = db.session.query(Digest).order_by(Digest.id)
            if limit:
                query = query.limit(limit)

            digests = query.all()
            total = len(digests)

            if total == 0:
                print("\n   No digests found in database")
                return 0

            print(f"\n   Found {total} digest(s) to process")

            # Get settings for graph service configuration
            from reconly_core.services.settings_service import SettingsService
            settings = SettingsService(db.session)

            semantic_threshold = settings.get("rag.graph.semantic_threshold")
            max_edges = settings.get("rag.graph.max_edges_per_digest")

            # Initialize services
            provider = get_embedding_provider(db=db.session)
            graph_service = GraphService(
                db=db.session,
                embedding_provider=provider,
                semantic_threshold=semantic_threshold,
                max_edges_per_digest=max_edges,
                default_chunk_source=chunk_source,
            )

            # Process digests in batches
            processed = 0
            total_relationships = 0
            errors = 0

            print("\n   Processing digests:")

            loop = asyncio.new_event_loop()
            try:
                for i, digest in enumerate(digests):
                    try:
                        title = digest.title[:40] if digest.title else f"Digest {digest.id}"
                        print(f"   [{i + 1}/{total}] {title}...", end=" ")

                        # Compute relationships
                        count = loop.run_until_complete(
                            graph_service.compute_relationships(
                                digest_id=digest.id,
                                include_semantic=True,
                                include_tags=include_tag_relationships,
                                include_source=include_source_relationships,
                                chunk_source=chunk_source,
                            )
                        )
                        total_relationships += count
                        processed += 1
                        print(f"{count} relationships")

                        # Commit after each batch
                        if (i + 1) % batch_size == 0:
                            db.session.commit()
                            print(f"   [Committed batch, {processed} digests processed]")

                    except Exception as e:
                        errors += 1
                        print(f"ERROR: {e}")
                        logger.error(f"Error processing digest {digest.id}: {e}")
                        continue

                # Final commit
                db.session.commit()

            finally:
                loop.close()

            # Print summary
            print("\n" + "=" * 60)
            print("REBUILD COMPLETE")
            print("=" * 60)
            print(f"   Digests processed: {processed}")
            print(f"   Relationships created: {total_relationships}")
            if errors > 0:
                print(f"   Errors: {errors}")

            # Show updated statistics
            stats = graph_service.get_statistics()
            print("\n   Graph Statistics:")
            print(f"      Total relationships: {stats['total_relationships']}")
            print(f"      By type: {stats['by_type']}")
            print(f"      Average score: {stats['average_score']}")
            print(f"      Coverage: {stats['coverage'] * 100:.1f}%")

            return 0 if errors == 0 else 1

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to rebuild knowledge graph")
            return 1

    def handle_backfill_source_content(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False,
        refetch: bool = False,
    ) -> int:
        """
        Backfill source content for historical digests.

        Finds digests with DigestSourceItems but no SourceContent records.

        Note: We cannot truly backfill content since the original content wasn't
        stored. This command either:
        1. Informs the user about the limitation (default)
        2. Optionally attempts to re-fetch content from URLs if --refetch is set

        Args:
            limit: Maximum number of items to process
            dry_run: If True, only show what would be done
            refetch: If True, attempt to re-fetch content from original URLs

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.database.models import DigestSourceItem, SourceContent

            print("Checking for historical source content to backfill...")

            db = DigestDB(database_url=self.database_url)

            # Find DigestSourceItems without SourceContent
            subquery = db.session.query(SourceContent.digest_source_item_id)
            query = db.session.query(DigestSourceItem).filter(
                ~DigestSourceItem.id.in_(subquery)
            )

            if limit:
                query = query.limit(limit)

            items = query.all()
            total = len(items)

            if total == 0:
                print("   All source items already have content stored.")
                print("   No backfill needed.")
                return 0

            print(f"\n   Found {total} source item(s) without stored content")

            if not refetch:
                # Default: explain the limitation
                print("\n" + "-" * 60)
                print("IMPORTANT: Historical Content Limitation")
                print("-" * 60)
                print("""
   Source content was not stored when these digests were originally
   created. The original fetched content is no longer available.

   Options:
   1. New digests will automatically store source content going forward.
   2. Use --refetch to attempt re-fetching from original URLs (may fail
      if content has changed, URLs are unavailable, or rate limits apply).

   Example:
      reconly --rag-backfill-source-content --refetch --limit 10
""")
                # Show sample of affected items
                print("   Sample of affected source items:")
                for item in items[:5]:
                    title = item.item_title[:50] if item.item_title else "(no title)"
                    print(f"      - [{item.id}] {title}")
                    print(f"        URL: {item.item_url[:60]}...")
                if total > 5:
                    print(f"      ... and {total - 5} more")

                return 0

            # Re-fetch mode
            if dry_run:
                print("\n   DRY RUN - would attempt to re-fetch:")
                for item in items[:10]:
                    title = item.item_title[:50] if item.item_title else "(no title)"
                    print(f"      - [{item.id}] {title}")
                if total > 10:
                    print(f"      ... and {total - 10} more")
                return 0

            print("\n   Attempting to re-fetch content from original URLs...")
            print("   Note: This may take a while and some URLs may no longer be available.\n")

            from datetime import datetime
            from hashlib import sha256
            from reconly_core.fetchers import get_fetcher

            successful = 0
            failed = 0

            for i, item in enumerate(items):
                try:
                    title = item.item_title[:40] if item.item_title else f"Item {item.id}"
                    print(f"   [{i + 1}/{total}] {title}...", end=" ")

                    # Use website fetcher to re-fetch content from URL
                    url = item.item_url
                    if not url:
                        print("SKIP (no URL)")
                        failed += 1
                        continue

                    try:
                        fetcher = get_fetcher('website')
                    except ValueError:
                        print("SKIP (no fetcher)")
                        failed += 1
                        continue

                    # Fetch content
                    fetched_items = fetcher.fetch(url)
                    fetched_item = fetched_items[0] if fetched_items else None

                    if not fetched_item or not fetched_item.content:
                        print("SKIP (no content)")
                        failed += 1
                        continue

                    content = fetched_item.content
                    content_hash = sha256(content.encode('utf-8')).hexdigest()

                    # Create SourceContent record
                    source_content = SourceContent(
                        digest_source_item_id=item.id,
                        content=content,
                        content_hash=content_hash,
                        content_length=len(content),
                        fetched_at=datetime.utcnow(),
                    )
                    db.session.add(source_content)
                    successful += 1
                    print(f"OK ({len(content)} chars)")

                    # Commit periodically
                    if (i + 1) % 10 == 0:
                        db.session.commit()

                except Exception as e:
                    failed += 1
                    print(f"ERROR: {e}")
                    logger.warning(f"Failed to re-fetch content for item {item.id}: {e}")
                    continue

            # Final commit
            db.session.commit()

            print("\n" + "=" * 60)
            print("BACKFILL COMPLETE")
            print("=" * 60)
            print(f"   Successfully re-fetched: {successful}")
            print(f"   Failed/skipped: {failed}")

            if successful > 0:
                print("\n   Next step: Run embedding to process new source content:")
                print("      reconly --rag-embed-source-content")

            return 0 if failed == 0 else 1

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to backfill source content")
            return 1

    def handle_embed_source_content(
        self,
        limit: Optional[int] = None,
        include_failed: bool = False,
    ) -> int:
        """
        Embed source content that hasn't been embedded yet.

        Finds SourceContent records without embeddings and processes them.

        Args:
            limit: Maximum number of source contents to process
            include_failed: Also retry previously failed embeddings

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.rag import EmbeddingService

            print("Looking for source content to embed...")

            db = DigestDB(database_url=self.database_url)
            service = EmbeddingService(db.session)

            # Get statistics first
            stats = service.get_chunk_statistics()
            source_stats = stats.get('source_contents', {})
            status = source_stats.get('embedding_status', {})

            not_started = status.get('not_started', 0)
            failed = status.get('failed', 0)

            to_process = not_started
            if include_failed:
                to_process += failed

            if to_process == 0:
                print("   All source content is already embedded!")
                return 0

            print(f"   Source content without embeddings: {not_started}")
            if include_failed:
                print(f"   Previously failed: {failed}")
            print(f"   Total to process: {to_process}")
            if limit:
                print(f"   Limit: {limit}")

            # Progress callback
            def progress_callback(current: int, total: int, source_content):
                length = source_content.content_length
                print(f"   [{current}/{total}] Embedding source content (length: {length})...")

            print("\n   Starting embedding process...\n")

            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(
                    service.embed_unembedded_source_contents(
                        limit=limit,
                        include_failed=include_failed,
                        progress_callback=progress_callback,
                    )
                )
                db.session.commit()
            finally:
                loop.close()

            # Count results
            successful = sum(1 for chunks in results.values() if chunks)
            failed_count = sum(1 for chunks in results.values() if not chunks)

            print("\n   Embedding Summary:")
            print(f"      Successfully embedded: {successful}")
            if failed_count > 0:
                print(f"      Failed: {failed_count}")

            print("\n   Embedding complete!")
            return 0 if failed_count == 0 else 1

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to embed source content")
            return 1

    def handle_graph_stats(self) -> int:
        """
        Show knowledge graph statistics.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.rag import GraphService, get_embedding_provider

            db = DigestDB(database_url=self.database_url)
            provider = get_embedding_provider(db=db.session)
            graph_service = GraphService(db=db.session, embedding_provider=provider)

            stats = graph_service.get_statistics()

            print("Knowledge Graph Statistics:")
            print("=" * 60)
            print(f"\n   Total Relationships: {stats['total_relationships']}")
            print(f"   Digests with Relationships: {stats['digests_with_relationships']}")
            print(f"   Total Digests: {stats['total_digests']}")
            print(f"   Coverage: {stats['coverage'] * 100:.1f}%")
            print(f"   Average Score: {stats['average_score']}")

            print("\n   By Relationship Type:")
            for rel_type, count in stats.get('by_type', {}).items():
                print(f"      {rel_type}: {count}")

            return 0

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to get graph statistics")
            return 1

    def handle_source_content_stats(self) -> int:
        """
        Show source content and embedding statistics.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.rag import EmbeddingService

            db = DigestDB(database_url=self.database_url)
            service = EmbeddingService(db.session)

            stats = service.get_chunk_statistics()
            source_stats = stats.get('source_contents', {})
            status = source_stats.get('embedding_status', {})

            print("Source Content Statistics:")
            print("=" * 60)

            print("\n   Source Contents:")
            print(f"      Total: {source_stats.get('total_source_contents', 0)}")
            print(f"      With embeddings: {source_stats.get('source_contents_with_chunks', 0)}")
            print(f"      Without embeddings: {source_stats.get('source_contents_without_chunks', 0)}")

            print("\n   Embedding Status:")
            print(f"      Completed: {status.get('completed', 0)}")
            print(f"      Pending: {status.get('pending', 0)}")
            print(f"      Failed: {status.get('failed', 0)}")
            print(f"      Not started: {status.get('not_started', 0)}")

            print("\n   Chunks:")
            print(f"      Total chunks: {source_stats.get('total_chunks', 0)}")
            print(f"      Avg per source: {source_stats.get('avg_chunks_per_source_content', 0)}")
            print(f"      Avg tokens per chunk: {source_stats.get('avg_tokens_per_chunk', 0)}")

            print("\n   Provider:")
            print(f"      Name: {stats.get('embedding_provider', 'unknown')}")
            print(f"      Dimension: {stats.get('embedding_dimension', 'unknown')}")

            return 0

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to get source content statistics")
            return 1

    def handle_prune_relationships(
        self,
        min_score: Optional[float] = None,
        max_age_days: Optional[int] = None,
        max_edges_per_digest: Optional[int] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Prune low-quality relationships from the knowledge graph.

        Args:
            min_score: Remove relationships below this score
            max_age_days: Remove relationships older than this
            max_edges_per_digest: Keep only top N edges per digest
            dry_run: If True, only show what would be deleted

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            from reconly_core.rag import GraphService

            if not any([min_score, max_age_days, max_edges_per_digest]):
                print("Error: At least one pruning criterion required:")
                print("   --prune-min-score SCORE")
                print("   --prune-max-age DAYS")
                print("   --prune-max-edges COUNT")
                return 1

            print("Pruning knowledge graph relationships...")
            if min_score:
                print(f"   Min score threshold: {min_score}")
            if max_age_days:
                print(f"   Max age: {max_age_days} days")
            if max_edges_per_digest:
                print(f"   Max edges per digest: {max_edges_per_digest}")

            db = DigestDB(database_url=self.database_url)
            graph_service = GraphService(db=db.session)

            # Get before stats
            before_stats = graph_service.get_statistics()
            print(f"\n   Current relationships: {before_stats['total_relationships']}")

            if dry_run:
                print("\n   DRY RUN - showing estimated impact")
                # For dry run, we can't easily estimate without modifying DB
                # Just show current stats
                print("   (Run without --dry-run to actually prune)")
                return 0

            # Perform pruning
            deleted = graph_service.prune_relationships(
                min_score=min_score,
                max_age_days=max_age_days,
                max_edges_per_digest=max_edges_per_digest,
            )
            db.session.commit()

            print(f"\n   Deleted: {deleted} relationships")

            # Get after stats
            after_stats = graph_service.get_statistics()
            print(f"   Remaining: {after_stats['total_relationships']}")

            return 0

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.exception("Failed to prune relationships")
            return 1
