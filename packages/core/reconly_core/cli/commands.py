"""Command handlers for CLI."""
import os
from typing import List, Optional
from reconly_core.services.digest_service import DigestService, ProcessOptions
from reconly_core.services.batch_service import BatchService, BatchOptions
from reconly_core.services.email_service import EmailService
from reconly_core.cli.output import OutputFormatter
from reconly_core.database.crud import DigestDB
from reconly_core.database.seed import seed_default_templates
from reconly_core.database.import_sources import import_sources_from_yaml
from reconly_core.services.feed_service import FeedService, FeedRunOptions


class CommandHandler:
    """Handles CLI commands."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize command handler.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.digest_service = DigestService(database_url=database_url)
        self.batch_service = BatchService()
        self.output = OutputFormatter()

    def handle_url(
        self,
        url: str,
        language: str = 'de',
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        enable_fallback: bool = True,
        show_cost: bool = False,
        save: bool = False,
        tags: Optional[List[str]] = None,
        reset_tracking: bool = False
    ) -> int:
        """
        Handle single URL processing.

        Args:
            url: URL to process
            language: Summary language
            provider: LLM provider
            model: Model to use
            api_key: API key
            enable_fallback: Enable fallback chain
            show_cost: Show cost information
            save: Save to database
            tags: Tags for digest
            reset_tracking: Reset RSS feed tracking

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            print(f"🔍 Fetching content from: {url}")

            # Detect source type
            source_type = self.digest_service._detect_source_type(url)

            if source_type == 'rss':
                print("📡 Detected RSS/Atom feed...")
            elif source_type == 'youtube':
                print("📺 Detected YouTube video...")
            else:
                print("🌐 Detected website...")

            # Create process options
            options = ProcessOptions(
                language=language,
                provider=provider,
                model=model,
                api_key=api_key,
                enable_fallback=enable_fallback,
                save=save,
                tags=tags,
                reset_tracking=reset_tracking
            )

            # Process URL
            result = self.digest_service.process_url(url, options)

            if not result.success:
                print(f"❌ Error: {result.error}")
                return 1

            # Handle RSS feed results (multiple articles)
            if source_type == 'rss' and result.data:
                articles = result.data.get('articles', [])

                if not articles:
                    print("✅ No new articles found!")
                    return 0

                print(f"✅ Found {len(articles)} new article(s)!")

                # Print each article summary
                for idx, article in enumerate(articles, 1):
                    if 'error' in article:
                        print(f"\n❌ Article {idx}/{len(articles)}: Error - {article['error']}")
                        continue

                    print(f"\n{'='*80}")
                    print(f"Processing article {idx}/{len(articles)}: {article['title']}")
                    print(f"{'='*80}")
                    print("✅ Summary generated!")

                    self.output.print_summary(article, article_num=idx, show_cost=show_cost)

                # Show tracking info
                if result.data.get('last_read'):
                    print(f"📅 Previous read: {result.data['last_read'].strftime('%Y-%m-%d %H:%M:%S')}")
                if result.data.get('new_last_read'):
                    print(f"✅ Tracking updated: {result.data['new_last_read'].strftime('%Y-%m-%d %H:%M:%S')}")

                print(f"\n🎉 Processed {len(articles)} article(s) successfully!")

            else:
                # Single result (website or YouTube)
                print("✅ Content fetched successfully!")
                if result.data:
                    print(f"   Title: {result.data['title']}")
                    print("\n🤖 Generating summary...")
                    print("✅ Summary generated successfully!")

                    self.output.print_summary(result.data, show_cost=show_cost)

                    if result.digest_id:
                        print(f"💾 Saved to database (ID: {result.digest_id})")

            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_search(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 10
    ) -> int:
        """
        Handle search command.

        Args:
            query: Search query
            tags: Filter by tags
            source_type: Filter by source type
            limit: Result limit

        Returns:
            Exit code
        """
        try:
            results = self.digest_service.search_digests(
                query=query,
                tags=tags,
                source_type=source_type,
                limit=limit
            )
            self.output.print_search_results(results, query, tags, source_type)
            return 0
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_list(
        self,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 10
    ) -> int:
        """
        Handle list command.

        Args:
            tags: Filter by tags
            source_type: Filter by source type
            limit: Result limit

        Returns:
            Exit code
        """
        try:
            results = self.digest_service.search_digests(
                tags=tags,
                source_type=source_type,
                limit=limit
            )
            self.output.print_list(results, tags, source_type, limit)
            return 0
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_stats(self) -> int:
        """
        Handle stats command.

        Returns:
            Exit code
        """
        try:
            stats = self.digest_service.get_statistics()
            self.output.print_statistics(stats)
            return 0
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_export(
        self,
        filename: str,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 1000
    ) -> int:
        """
        Handle export command.

        Args:
            filename: Output filename
            tags: Filter by tags
            source_type: Filter by source type
            limit: Result limit

        Returns:
            Exit code
        """
        try:
            print(f"📤 Exporting digests to {filename}")
            data = self.digest_service.export_digests(
                tags=tags,
                source_type=source_type,
                limit=limit
            )
            success = self.output.export_to_file(filename, data)
            return 0 if success else 1
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_send_digest(
        self,
        to_email: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 20,
        language: str = 'en'
    ) -> int:
        """
        Handle send digest email command.

        Args:
            to_email: Recipient email (default: from EMAIL_RECIPIENT env var)
            tags: Filter by tags
            source_type: Filter by source type
            limit: Number of recent digests to include
            language: Language for email template

        Returns:
            Exit code
        """
        try:
            # Get email from env if not provided
            recipient = to_email or os.getenv('EMAIL_RECIPIENT')
            if not recipient:
                print("❌ Error: No email recipient specified.")
                print("   Set EMAIL_RECIPIENT in .env or use --email flag")
                return 1

            print(f"📧 Preparing digest email to {recipient}")

            # Fetch recent digests
            digests_data = self.digest_service.export_digests(
                tags=tags,
                source_type=source_type,
                limit=limit
            )

            if not digests_data:
                print("⚠️  No digests found to send")
                return 0

            print(f"   Found {len(digests_data)} digest(s) to send")

            # Initialize email service
            email_service = EmailService()

            # Send digest email
            print("   Sending email...")
            success = email_service.send_digest_email(
                to_email=recipient,
                digests=digests_data,
                language=language
            )

            if success:
                print(f"✅ Digest email sent successfully to {recipient}")
                return 0
            else:
                print("❌ Failed to send email. Check SMTP configuration in .env")
                return 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_batch(
        self,
        config_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        language: str = 'de',
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        enable_fallback: bool = True,
        save: bool = False,
        show_progress: bool = True,
        delay_between: int = 2
    ) -> int:
        """
        Handle batch processing command.

        Args:
            config_path: Path to config file
            tags: Filter by tags
            source_type: Filter by source type
            language: Summary language
            provider: LLM provider
            model: Model to use
            api_key: API key
            enable_fallback: Enable fallback chain
            save: Save to database
            show_progress: Show progress
            delay_between: Delay between sources

        Returns:
            Exit code
        """
        try:
            # Create batch options
            options = BatchOptions(
                config_path=config_path,
                tags=tags,
                source_type=source_type,
                language=language,
                provider=provider,
                model=model,
                api_key=api_key,
                enable_fallback=enable_fallback,
                save=save,
                database_url=self.database_url,
                show_progress=show_progress,
                delay_between=delay_between
            )

            # Process batch
            result = self.batch_service.process_batch(options)

            # Print summary
            if result.total_sources > 0:
                self.output.print_batch_summary(
                    result.total_processed,
                    result.total_errors,
                    result.success_rate
                )
            else:
                # Handle errors
                for source_result in result.source_results:
                    if 'error' in source_result:
                        print(f"❌ {source_result['error']}")
                        if 'suggestion' in source_result:
                            print(f"💡 {source_result['suggestion']}")

            return 0 if result.total_errors == 0 else 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_init(
        self,
        seed_templates: bool = True
    ) -> int:
        """
        Initialize the database with schema and default templates.

        Args:
            seed_templates: Whether to seed default templates

        Returns:
            Exit code
        """
        try:
            print("🔧 Initializing Reconly database...")

            # Create database and tables via DigestDB (creates tables on init)
            db = DigestDB(database_url=self.database_url)
            print("✅ Database schema created")

            if seed_templates:
                print("🌱 Seeding default templates...")
                result = seed_default_templates(db.session)
                print(f"   Prompt templates: {result['prompt_templates_created']} created, {result['prompt_templates_skipped']} skipped")
                print(f"   Report templates: {result['report_templates_created']} created, {result['report_templates_skipped']} skipped")

            print("🎉 Database initialization complete!")
            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_import(
        self,
        config_path: Optional[str] = None,
        create_feed: bool = False,
        feed_name: Optional[str] = None,
        enabled_only: bool = True
    ) -> int:
        """
        Import sources from YAML configuration into the database.

        Args:
            config_path: Path to sources.yaml (default: config/sources.yaml)
            create_feed: Create a feed with all imported sources
            feed_name: Name for the created feed
            enabled_only: Only import enabled sources

        Returns:
            Exit code
        """
        try:
            print("📥 Importing sources from YAML...")

            if config_path:
                print(f"   Config file: {config_path}")

            # Get database session via DigestDB
            db = DigestDB(database_url=self.database_url)

            # Import sources
            result = import_sources_from_yaml(
                session=db.session,
                config_path=config_path,
                user_id=None,  # Single user mode
                create_feed=create_feed,
                feed_name=feed_name,
                skip_existing=True,
                enabled_only=enabled_only,
            )

            # Print results
            print("\n📊 Import Summary:")
            print(f"   Sources created: {result.sources_created}")
            print(f"   Sources skipped: {result.sources_skipped} (already exist)")
            print(f"   Sources failed:  {result.sources_failed}")

            if result.feed_created:
                print(f"\n📰 Created feed: '{feed_name or 'Imported Feed'}' (ID: {result.feed_id})")
                print(f"   Contains {result.total_sources - result.sources_failed} sources")

            if result.errors:
                print("\n⚠️  Errors:")
                for error in result.errors:
                    print(f"   - {error}")

            if result.sources_created > 0 or result.sources_skipped > 0:
                print("\n✅ Import complete!")
                return 0
            else:
                print("\n❌ No sources imported")
                return 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_sources_list(self) -> int:
        """
        List all sources in the database.

        Returns:
            Exit code
        """
        try:
            from reconly_core.database.models import Source

            db = DigestDB(database_url=self.database_url)
            sources = db.session.query(Source).all()

            if not sources:
                print("📭 No sources found in database")
                print("   Use 'reconly import' to import from YAML")
                return 0

            print(f"📚 Sources ({len(sources)} total):\n")

            for source in sources:
                status = "✅" if source.enabled else "⏸️"
                print(f"  {status} [{source.id}] {source.name}")
                print(f"      Type: {source.type} | URL: {source.url[:60]}...")
                if source.default_provider:
                    print(f"      Provider: {source.default_provider}/{source.default_model or 'default'}")
                print()

            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_feeds_list(self) -> int:
        """
        List all feeds in the database.

        Returns:
            Exit code
        """
        try:
            from reconly_core.database.models import Feed

            db = DigestDB(database_url=self.database_url)
            feeds = db.session.query(Feed).all()

            if not feeds:
                print("📭 No feeds found in database")
                print("   Use 'reconly import --create-feed' to create one")
                return 0

            print(f"📰 Feeds ({len(feeds)} total):\n")

            for feed in feeds:
                status = "✅" if feed.schedule_enabled else "⏸️"
                schedule = feed.schedule_cron or "manual"
                sources_count = len(feed.feed_sources) if feed.feed_sources else 0

                print(f"  {status} [{feed.id}] {feed.name}")
                print(f"      Schedule: {schedule} | Sources: {sources_count}")
                if feed.last_run_at:
                    print(f"      Last run: {feed.last_run_at.strftime('%Y-%m-%d %H:%M')}")
                if feed.description:
                    print(f"      {feed.description[:60]}...")
                print()

            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_run_feed(
        self,
        feed_id: int,
        api_key: Optional[str] = None,
        enable_fallback: bool = True
    ) -> int:
        """
        Run a specific feed by ID.

        Args:
            feed_id: Feed ID to run
            api_key: Optional API key for LLM provider
            enable_fallback: Enable fallback chain

        Returns:
            Exit code
        """
        try:
            # Initialize feed service
            feed_service = FeedService(database_url=self.database_url)

            # Check feed exists
            feed = feed_service.get_feed(feed_id)
            if not feed:
                print(f"❌ Feed not found: {feed_id}")
                print("   Use 'reconly --feeds' to list available feeds")
                return 1

            # Create run options
            options = FeedRunOptions(
                triggered_by="manual",
                api_key=api_key,
                enable_fallback=enable_fallback,
                show_progress=True,
            )

            # Run the feed
            result = feed_service.run_feed(feed_id, options)

            # Print final summary
            if result.errors:
                print(f"\n⚠️  Completed with {len(result.errors)} error(s)")
                return 1
            else:
                return 0

        except Exception as e:
            print(f"❌ Error running feed: {str(e)}")
            return 1

    def handle_usage_stats(self) -> int:
        """
        Show LLM usage statistics.

        Returns:
            Exit code
        """
        try:
            feed_service = FeedService(database_url=self.database_url)
            stats = feed_service.get_usage_stats()

            print("📊 LLM Usage Statistics:\n")
            print(f"   Total Requests: {stats['total_requests']}")
            print(f"   Total Tokens In: {stats['total_tokens_in']:,}")
            print(f"   Total Tokens Out: {stats['total_tokens_out']:,}")
            print(f"   Total Cost: ${stats['total_cost']:.4f}")

            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_embed_all(
        self,
        limit: Optional[int] = None,
        include_failed: bool = False
    ) -> int:
        """
        Backfill embeddings for all unembedded digests.

        Args:
            limit: Maximum number of digests to process (None = all)
            include_failed: Also retry previously failed embeddings

        Returns:
            Exit code
        """
        import asyncio

        try:
            from reconly_core.rag import EmbeddingService

            print("🔍 Looking for digests to embed...")

            db = DigestDB(database_url=self.database_url)
            service = EmbeddingService(db.session)

            # Get statistics first
            stats = service.get_chunk_statistics()
            status = stats.get('embedding_status', {})

            not_started = status.get('not_started', 0)
            failed = status.get('failed', 0)

            to_process = not_started
            if include_failed:
                to_process += failed

            if to_process == 0:
                print("✅ All digests are already embedded!")
                return 0

            print(f"   Digests without embeddings: {not_started}")
            if include_failed:
                print(f"   Previously failed digests: {failed}")
            print(f"   Total to process: {to_process}")
            if limit:
                print(f"   Limit: {limit}")

            # Progress callback for CLI output
            def progress_callback(current: int, total: int, digest):
                title = digest.title[:50] if digest.title else 'Untitled'
                print(f"   [{current}/{total}] Embedding: {title}...")

            print("\n📦 Starting embedding process...\n")

            # Run embedding
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(
                    service.embed_unembedded_digests(
                        limit=limit,
                        include_failed=include_failed,
                        progress_callback=progress_callback,
                    )
                )
                db.session.commit()
            finally:
                loop.close()

            # Count successes and failures
            successful = sum(1 for chunks in results.values() if chunks)
            failed_count = sum(1 for chunks in results.values() if not chunks)

            print("\n📊 Embedding Summary:")
            print(f"   Successfully embedded: {successful}")
            if failed_count > 0:
                print(f"   Failed: {failed_count}")

            print("\n✅ Embedding complete!")
            return 0 if failed_count == 0 else 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1

    def handle_embed_stats(self) -> int:
        """
        Show embedding statistics.

        Returns:
            Exit code
        """
        try:
            from reconly_core.rag import EmbeddingService

            db = DigestDB(database_url=self.database_url)
            service = EmbeddingService(db.session)

            stats = service.get_chunk_statistics()
            status = stats.get('embedding_status', {})

            print("📊 Embedding Statistics:\n")

            print("   Digests:")
            print(f"      Total: {stats['total_digests']}")
            print(f"      With embeddings: {stats['digests_with_chunks']}")
            print(f"      Without embeddings: {stats['digests_without_chunks']}")

            print("\n   Embedding Status:")
            print(f"      Completed: {status.get('completed', 0)}")
            print(f"      Pending: {status.get('pending', 0)}")
            print(f"      Failed: {status.get('failed', 0)}")
            print(f"      Not started: {status.get('not_started', 0)}")

            print("\n   Chunks:")
            print(f"      Total chunks: {stats['total_chunks']}")
            print(f"      Avg per digest: {stats['avg_chunks_per_digest']}")
            print(f"      Avg tokens per chunk: {stats['avg_tokens_per_chunk']}")

            print("\n   Provider:")
            print(f"      Name: {stats['embedding_provider']}")
            print(f"      Dimension: {stats['embedding_dimension']}")

            return 0

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1
