"""Feed bundle exporter for marketplace.

Exports a Feed (with its sources, templates, schedule) as a portable JSON bundle.
"""
import json
from typing import Optional

from reconly_core.database.models import Feed, PromptTemplate, ReportTemplate
from reconly_core.marketplace.bundle import (
    FeedBundle,
    BundleAuthor,
    BundleSource,
    BundlePromptTemplate,
    BundleReportTemplate,
    BundleSchedule,
    BundleCompatibility,
    BundleMetadata,
    slugify,
)


class FeedBundleExporter:
    """Exports feeds as portable JSON bundles for marketplace sharing."""

    def __init__(
        self,
        author_name: str = "Anonymous",
        author_github: Optional[str] = None,
        author_email: Optional[str] = None,
    ):
        """Initialize exporter with author information.

        Args:
            author_name: Bundle author name
            author_github: Optional GitHub username
            author_email: Optional email address
        """
        self.author = BundleAuthor(
            name=author_name,
            github=author_github,
            email=author_email,
        )

    def export_feed(
        self,
        feed: Feed,
        version: str = "1.0.0",
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        min_reconly_version: Optional[str] = None,
        required_features: Optional[list[str]] = None,
        license_name: Optional[str] = None,
        homepage: Optional[str] = None,
        repository: Optional[str] = None,
    ) -> FeedBundle:
        """Export a feed as a FeedBundle.

        Args:
            feed: Feed model instance with loaded relationships
            version: Semantic version for the bundle (default: 1.0.0)
            category: Bundle category (news, tech, finance, etc.)
            tags: List of tags for discovery
            min_reconly_version: Minimum Reconly version required
            required_features: List of required features (e.g., ['ollama', 'email'])
            license_name: License identifier (e.g., 'MIT', 'CC-BY-4.0')
            homepage: Bundle homepage URL
            repository: Bundle repository URL

        Returns:
            FeedBundle ready for JSON serialization
        """
        # Export sources
        sources = self._export_sources(feed)

        # Export prompt template if assigned
        prompt_template = None
        if feed.prompt_template:
            prompt_template = self._export_prompt_template(feed.prompt_template)

        # Export report template if assigned
        report_template = None
        if feed.report_template:
            report_template = self._export_report_template(feed.report_template)

        # Export schedule
        schedule = None
        if feed.schedule_cron:
            schedule = BundleSchedule(
                cron=feed.schedule_cron,
                description=f"Scheduled feed: {feed.name}",
            )

        # Build compatibility
        compatibility = None
        if min_reconly_version or required_features:
            compatibility = BundleCompatibility(
                min_reconly_version=min_reconly_version,
                required_features=required_features or [],
            )

        # Build metadata
        metadata = None
        if license_name or homepage or repository:
            metadata = BundleMetadata(
                license=license_name,
                homepage=homepage,
                repository=repository,
            )

        # Detect primary language from prompt template or first source
        language = None
        if prompt_template:
            language = prompt_template.language
        elif sources:
            # Check first source for default_language
            language = sources[0].default_language

        return FeedBundle(
            id=slugify(feed.name),
            name=feed.name,
            version=version,
            description=feed.description,
            author=self.author,
            category=category,
            tags=tags or [],
            language=language,
            sources=sources,
            prompt_template=prompt_template,
            report_template=report_template,
            schedule=schedule,
            output_config=self._sanitize_output_config(feed.output_config),
            digest_mode=feed.digest_mode or "individual",
            compatibility=compatibility,
            metadata=metadata,
        )

    def export_feed_to_json(
        self,
        feed: Feed,
        **kwargs,
    ) -> str:
        """Export a feed directly to JSON string.

        Args:
            feed: Feed model instance
            **kwargs: Additional arguments passed to export_feed()

        Returns:
            JSON string of the bundle
        """
        bundle = self.export_feed(feed, **kwargs)
        return json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False)

    def export_feed_to_dict(
        self,
        feed: Feed,
        **kwargs,
    ) -> dict:
        """Export a feed directly to dictionary.

        Args:
            feed: Feed model instance
            **kwargs: Additional arguments passed to export_feed()

        Returns:
            Dictionary representation of the bundle
        """
        bundle = self.export_feed(feed, **kwargs)
        return bundle.to_dict()

    def _export_sources(self, feed: Feed) -> list[BundleSource]:
        """Export feed sources to bundle format.

        Args:
            feed: Feed with loaded feed_sources relationship

        Returns:
            List of BundleSource instances
        """
        sources = []
        for feed_source in feed.feed_sources:
            if not feed_source.enabled:
                continue

            source = feed_source.source
            bundle_source = BundleSource(
                name=source.name,
                type=source.type,
                url=source.url,
                config=source.config,
                default_language=source.default_language,
                include_keywords=source.include_keywords,
                exclude_keywords=source.exclude_keywords,
                filter_mode=source.filter_mode,
                use_regex=source.use_regex or False,
            )
            sources.append(bundle_source)

        return sources

    def _export_prompt_template(self, template: PromptTemplate) -> BundlePromptTemplate:
        """Export prompt template to bundle format.

        Args:
            template: PromptTemplate model instance

        Returns:
            BundlePromptTemplate instance
        """
        return BundlePromptTemplate(
            name=template.name,
            description=template.description,
            system_prompt=template.system_prompt,
            user_prompt_template=template.user_prompt_template,
            language=template.language or "en",
            target_length=template.target_length or 150,
        )

    def _export_report_template(self, template: ReportTemplate) -> BundleReportTemplate:
        """Export report template to bundle format.

        Args:
            template: ReportTemplate model instance

        Returns:
            BundleReportTemplate instance
        """
        return BundleReportTemplate(
            name=template.name,
            description=template.description,
            format=template.format or "markdown",
            template_content=template.template_content,
        )

    def _sanitize_output_config(self, config: Optional[dict]) -> Optional[dict]:
        """Sanitize output config for export.

        Removes sensitive data like specific email addresses while preserving
        the structure to indicate what outputs are configured.

        Args:
            config: Raw output_config from Feed

        Returns:
            Sanitized config dict or None
        """
        if not config:
            return None

        sanitized = {}

        # Preserve db flag
        if "db" in config:
            sanitized["db"] = config["db"]

        # Sanitize email config (remove actual addresses)
        if "email" in config and isinstance(config["email"], dict):
            email_config = {"enabled": config["email"].get("enabled", False)}
            # Don't include actual recipient addresses
            sanitized["email"] = email_config

        # Preserve other non-sensitive config keys
        # (add more as needed, but be careful with paths, credentials, etc.)

        return sanitized if sanitized else None
