"""Batch processing service for multiple sources."""
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from reconly_core.config import load_config, SourceConfig
from reconly_core.services.digest_service import DigestService, ProcessOptions


@dataclass
class BatchOptions:
    """Options for batch processing."""
    config_path: Optional[str] = None
    tags: Optional[List[str]] = None
    source_type: Optional[str] = None
    language: str = 'de'
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    enable_fallback: bool = True
    save: bool = False
    database_url: Optional[str] = None
    show_progress: bool = True
    delay_between: int = 2


@dataclass
class BatchResult:
    """Result of batch processing."""
    total_sources: int
    total_processed: int
    total_errors: int
    source_results: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.total_processed + self.total_errors
        if total == 0:
            return 0.0
        return (self.total_processed / total) * 100


class BatchService:
    """Service for batch processing multiple sources."""

    def __init__(self):
        """Initialize batch service."""
        self.digest_service: Optional[DigestService] = None

    def _get_digest_service(self, database_url: Optional[str] = None) -> DigestService:
        """Get or create digest service."""
        if self.digest_service is None:
            self.digest_service = DigestService(database_url=database_url)
        return self.digest_service

    def process_batch(self, options: BatchOptions) -> BatchResult:
        """
        Process multiple sources from configuration.

        Args:
            options: Batch processing options

        Returns:
            BatchResult with processing statistics
        """
        try:
            # Load configuration
            config = load_config(options.config_path)

            # Get sources (filter by tags/type if provided)
            sources = self._filter_sources(config, options)

            if not sources:
                return BatchResult(
                    total_sources=0,
                    total_processed=0,
                    total_errors=1,
                    source_results=[{
                        'error': 'No enabled sources found in config'
                    }]
                )

            # Get batch settings from config
            batch_settings = config.settings.get('batch', {})
            delay = options.delay_between or batch_settings.get('delay_between', 2)
            show_progress = options.show_progress and batch_settings.get('show_progress', True)

            # Check if auto-save is enabled in config
            auto_save = config.settings.get('auto_save', False) or options.save

            # Get default provider/model from config if not specified
            provider = options.provider or config.settings.get('provider', 'huggingface')
            model = options.model or config.settings.get('model', 'glm-4')
            language = options.language or config.settings.get('language', 'de')

            # Initialize digest service
            digest_service = self._get_digest_service(options.database_url)

            # Statistics
            total_processed = 0
            total_errors = 0
            source_results = []

            # Process each source
            for idx, source in enumerate(sources, 1):
                source_result = self._process_source(
                    source=source,
                    digest_service=digest_service,
                    global_provider=provider,
                    global_model=model,
                    global_language=language,
                    global_tags=options.tags,
                    auto_save=auto_save,
                    api_key=options.api_key,
                    enable_fallback=options.enable_fallback,
                    show_progress=show_progress,
                    source_num=idx,
                    total_sources=len(sources)
                )

                source_results.append(source_result)
                total_processed += source_result.get('items_processed', 0)
                total_errors += source_result.get('items_failed', 0)

                # Delay between sources (except after last one)
                if idx < len(sources) and delay > 0:
                    if show_progress:
                        print(f"⏱️  Waiting {delay}s before next source...")
                    time.sleep(delay)

            return BatchResult(
                total_sources=len(sources),
                total_processed=total_processed,
                total_errors=total_errors,
                source_results=source_results
            )

        except FileNotFoundError as e:
            return BatchResult(
                total_sources=0,
                total_processed=0,
                total_errors=1,
                source_results=[{
                    'error': f'Config file not found: {e}',
                    'suggestion': 'Create config/sources.yaml from config/sources.example.yaml'
                }]
            )
        except Exception as e:
            return BatchResult(
                total_sources=0,
                total_processed=0,
                total_errors=1,
                source_results=[{
                    'error': f'Batch processing error: {str(e)}'
                }]
            )

    def _filter_sources(self, config, options: BatchOptions) -> List[SourceConfig]:
        """Filter sources based on options."""
        if options.tags:
            return config.get_sources_by_tag(options.tags)
        elif options.source_type:
            return config.get_sources_by_type(options.source_type)
        else:
            return config.enabled_sources

    def _process_source(
        self,
        source: SourceConfig,
        digest_service: DigestService,
        global_provider: str,
        global_model: str,
        global_language: str,
        global_tags: Optional[List[str]],
        auto_save: bool,
        api_key: Optional[str],
        enable_fallback: bool,
        show_progress: bool,
        source_num: int,
        total_sources: int
    ) -> Dict[str, Any]:
        """
        Process a single source.

        Returns:
            Dictionary with source result information
        """
        if show_progress:
            print(f"\n{'='*80}")
            print(f"📌 Source {source_num}/{total_sources}: {source.name}")
            print(f"{'='*80}")
            print(f"🔗 URL: {source.url}")
            print(f"📑 Type: {source.type.upper()}")
            if source.tags:
                print(f"🏷️  Tags: {', '.join(source.tags)}")

        try:
            # Get source-specific settings or use global settings
            src_language = source.language or global_language
            src_provider = source.provider or global_provider
            src_model = source.model or global_model

            # Determine source tags (merge source tags with global tags)
            source_tags = source.tags.copy() if source.tags else []
            if global_tags:
                source_tags.extend(global_tags)
            source_tags = list(set(source_tags))  # Remove duplicates

            # Create process options
            process_options = ProcessOptions(
                language=src_language,
                provider=src_provider,
                model=src_model,
                api_key=api_key,
                enable_fallback=enable_fallback,
                save=auto_save,
                tags=source_tags if source_tags else None
            )

            # Process the source
            result = digest_service.process_url(source.url, process_options)

            if result.success:
                # Count items processed
                if source.type == 'rss' and result.data:
                    items_count = result.data.get('count', 0)
                    if show_progress:
                        print(f"✅ Processed {items_count} article(s)")
                    return {
                        'source': source.name,
                        'url': source.url,
                        'type': source.type,
                        'success': True,
                        'items_processed': items_count,
                        'items_failed': 0
                    }
                else:
                    if show_progress:
                        print("✅ Processed successfully")
                    return {
                        'source': source.name,
                        'url': source.url,
                        'type': source.type,
                        'success': True,
                        'items_processed': 1,
                        'items_failed': 0
                    }
            else:
                if show_progress:
                    print(f"❌ Error: {result.error}")
                return {
                    'source': source.name,
                    'url': source.url,
                    'type': source.type,
                    'success': False,
                    'items_processed': 0,
                    'items_failed': 1,
                    'error': result.error
                }

        except Exception as e:
            if show_progress:
                print(f"❌ Error processing source: {str(e)}")
            return {
                'source': source.name,
                'url': source.url,
                'type': source.type,
                'success': False,
                'items_processed': 0,
                'items_failed': 1,
                'error': str(e)
            }
