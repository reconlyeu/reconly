"""Feed bundle importer for marketplace.

Imports a portable JSON bundle to create a new Feed with sources and templates.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from reconly_core.database.models import Feed, Source, FeedSource, PromptTemplate, ReportTemplate
from reconly_core.marketplace.bundle import FeedBundle
from reconly_core.marketplace.validator import BundleValidator


@dataclass
class ImportResult:
    """Result of bundle import operation."""
    success: bool
    feed_id: Optional[int] = None
    feed_name: Optional[str] = None
    sources_created: int = 0
    prompt_template_id: Optional[int] = None
    report_template_id: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


class FeedBundleImporter:
    """Imports feed bundles from marketplace JSON format."""

    def __init__(self, db: Session):
        """Initialize importer with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.validator = BundleValidator()

    def import_bundle(
        self,
        data: dict,
        user_id: Optional[int] = None,
        validate_first: bool = True,
        skip_duplicate_sources: bool = True,
    ) -> ImportResult:
        """Import a bundle to create Feed, Sources, and Templates.

        Args:
            data: Parsed bundle JSON data
            user_id: Optional user ID to associate with created entities
            validate_first: Whether to validate bundle before import
            skip_duplicate_sources: If True, reuse existing sources with same URL

        Returns:
            ImportResult with created entity IDs and any errors/warnings
        """
        result = ImportResult(success=True)

        # Validate if requested
        if validate_first:
            validation = self.validator.validate(data)
            if not validation.is_valid:
                result.errors = validation.errors
                result.warnings = validation.warnings
                result.success = False
                return result
            result.warnings = validation.warnings

        # Parse bundle
        try:
            bundle = FeedBundle.from_dict(data)
        except (KeyError, TypeError, ValueError) as e:
            result.add_error(f"Failed to parse bundle: {e}")
            return result

        # Check for duplicate feed name
        existing_feed = self.db.query(Feed).filter(Feed.name == bundle.name).first()
        if existing_feed:
            result.add_error(f"A feed with name '{bundle.name}' already exists (id={existing_feed.id})")
            return result

        try:
            # Create sources
            source_ids = self._create_sources(bundle, user_id, skip_duplicate_sources, result)
            if not result.success:
                return result

            # Create prompt template if present
            prompt_template_id = None
            if bundle.prompt_template:
                prompt_template_id = self._create_prompt_template(bundle, user_id, result)
                if not result.success:
                    return result
                result.prompt_template_id = prompt_template_id

            # Create report template if present
            report_template_id = None
            if bundle.report_template:
                report_template_id = self._create_report_template(bundle, user_id, result)
                if not result.success:
                    return result
                result.report_template_id = report_template_id

            # Create feed
            feed = self._create_feed(
                bundle,
                source_ids,
                prompt_template_id,
                report_template_id,
                user_id,
                result,
            )
            if not result.success:
                return result

            # Commit all changes
            self.db.commit()

            result.feed_id = feed.id
            result.feed_name = feed.name
            result.sources_created = len(source_ids)

        except Exception as e:
            self.db.rollback()
            result.add_error(f"Database error during import: {e}")

        return result

    def import_from_json(
        self,
        json_str: str,
        user_id: Optional[int] = None,
        **kwargs,
    ) -> ImportResult:
        """Import a bundle from JSON string.

        Args:
            json_str: JSON string of the bundle
            user_id: Optional user ID to associate with created entities
            **kwargs: Additional arguments passed to import_bundle()

        Returns:
            ImportResult with created entity IDs and any errors/warnings
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            result = ImportResult(success=False)
            result.add_error(f"Invalid JSON: {e}")
            return result

        return self.import_bundle(data, user_id=user_id, **kwargs)

    def _create_sources(
        self,
        bundle: FeedBundle,
        user_id: Optional[int],
        skip_duplicate: bool,
        result: ImportResult,
    ) -> list[int]:
        """Create sources from bundle.

        Args:
            bundle: FeedBundle with sources
            user_id: Optional user ID
            skip_duplicate: If True, reuse existing sources with same URL
            result: ImportResult to add warnings to

        Returns:
            List of source IDs (new or existing)
        """
        source_ids = []

        for bundle_source in bundle.sources:
            # Check for existing source by URL
            if skip_duplicate:
                existing = self.db.query(Source).filter(Source.url == bundle_source.url).first()
                if existing:
                    result.add_warning(
                        f"Reusing existing source '{existing.name}' (id={existing.id}) for URL: {bundle_source.url}"
                    )
                    source_ids.append(existing.id)
                    continue

            # Create new source
            source = Source(
                user_id=user_id,
                name=bundle_source.name,
                type=bundle_source.type,
                url=bundle_source.url,
                config=bundle_source.config,
                default_language=bundle_source.default_language,
                include_keywords=bundle_source.include_keywords,
                exclude_keywords=bundle_source.exclude_keywords,
                filter_mode=bundle_source.filter_mode,
                use_regex=bundle_source.use_regex,
                enabled=True,
            )
            self.db.add(source)
            self.db.flush()  # Get the ID without committing
            source_ids.append(source.id)

        return source_ids

    def _create_prompt_template(
        self,
        bundle: FeedBundle,
        user_id: Optional[int],
        result: ImportResult,
    ) -> Optional[int]:
        """Create prompt template from bundle.

        Args:
            bundle: FeedBundle with prompt_template
            user_id: Optional user ID
            result: ImportResult to add warnings to

        Returns:
            Created template ID or None
        """
        pt = bundle.prompt_template
        if not pt:
            return None

        # Generate unique name if needed
        template_name = f"{pt.name} ({bundle.provenance_string})"

        # Check for existing template with same provenance
        existing = self.db.query(PromptTemplate).filter(
            PromptTemplate.imported_from_bundle == bundle.provenance_string
        ).first()
        if existing:
            result.add_warning(
                f"Reusing existing prompt template '{existing.name}' (id={existing.id}) from same bundle"
            )
            return existing.id

        template = PromptTemplate(
            user_id=user_id,
            name=template_name,
            description=pt.description,
            system_prompt=pt.system_prompt,
            user_prompt_template=pt.user_prompt_template,
            language=pt.language,
            target_length=pt.target_length,
            origin='imported',
            imported_from_bundle=bundle.provenance_string,
            is_active=True,
        )
        self.db.add(template)
        self.db.flush()
        return template.id

    def _create_report_template(
        self,
        bundle: FeedBundle,
        user_id: Optional[int],
        result: ImportResult,
    ) -> Optional[int]:
        """Create report template from bundle.

        Args:
            bundle: FeedBundle with report_template
            user_id: Optional user ID
            result: ImportResult to add warnings to

        Returns:
            Created template ID or None
        """
        rt = bundle.report_template
        if not rt:
            return None

        # Generate unique name if needed
        template_name = f"{rt.name} ({bundle.provenance_string})"

        # Check for existing template with same provenance
        existing = self.db.query(ReportTemplate).filter(
            ReportTemplate.imported_from_bundle == bundle.provenance_string
        ).first()
        if existing:
            result.add_warning(
                f"Reusing existing report template '{existing.name}' (id={existing.id}) from same bundle"
            )
            return existing.id

        template = ReportTemplate(
            user_id=user_id,
            name=template_name,
            description=rt.description,
            format=rt.format,
            template_content=rt.template_content,
            origin='imported',
            imported_from_bundle=bundle.provenance_string,
            is_active=True,
        )
        self.db.add(template)
        self.db.flush()
        return template.id

    def _create_feed(
        self,
        bundle: FeedBundle,
        source_ids: list[int],
        prompt_template_id: Optional[int],
        report_template_id: Optional[int],
        user_id: Optional[int],
        result: ImportResult,
    ) -> Feed:
        """Create feed from bundle.

        Args:
            bundle: FeedBundle
            source_ids: List of source IDs to link
            prompt_template_id: Optional prompt template ID
            report_template_id: Optional report template ID
            user_id: Optional user ID
            result: ImportResult to add warnings to

        Returns:
            Created Feed instance
        """
        # Extract schedule cron
        schedule_cron = None
        if bundle.schedule and bundle.schedule.cron:
            schedule_cron = bundle.schedule.cron

        feed = Feed(
            user_id=user_id,
            name=bundle.name,
            description=bundle.description,
            digest_mode=bundle.digest_mode,
            schedule_cron=schedule_cron,
            schedule_enabled=schedule_cron is not None,
            prompt_template_id=prompt_template_id,
            report_template_id=report_template_id,
            output_config=bundle.output_config,
        )
        self.db.add(feed)
        self.db.flush()

        # Create FeedSource junction records
        for i, source_id in enumerate(source_ids):
            feed_source = FeedSource(
                feed_id=feed.id,
                source_id=source_id,
                enabled=True,
                priority=len(source_ids) - i,  # First source has highest priority
            )
            self.db.add(feed_source)

        return feed

    def preview_import(self, data: dict) -> dict:
        """Preview what would be created without actually importing.

        Args:
            data: Parsed bundle JSON data

        Returns:
            Dictionary describing what would be created
        """
        validation = self.validator.validate(data)
        if not validation.is_valid:
            return {
                "valid": False,
                "errors": validation.errors,
                "warnings": validation.warnings,
            }

        try:
            bundle = FeedBundle.from_dict(data)
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Failed to parse bundle: {e}"],
                "warnings": [],
            }

        # Check for existing entities
        existing_feed = self.db.query(Feed).filter(Feed.name == bundle.name).first()
        existing_sources = []
        new_sources = []
        for bs in bundle.sources:
            existing = self.db.query(Source).filter(Source.url == bs.url).first()
            if existing:
                existing_sources.append({"name": bs.name, "url": bs.url, "existing_id": existing.id})
            else:
                new_sources.append({"name": bs.name, "url": bs.url, "type": bs.type})

        return {
            "valid": True,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "feed": {
                "name": bundle.name,
                "id": bundle.id,
                "version": bundle.version,
                "description": bundle.description,
                "already_exists": existing_feed is not None,
            },
            "sources": {
                "total": len(bundle.sources),
                "new": new_sources,
                "existing": existing_sources,
            },
            "prompt_template": {
                "included": bundle.prompt_template is not None,
                "name": bundle.prompt_template.name if bundle.prompt_template else None,
            },
            "report_template": {
                "included": bundle.report_template is not None,
                "name": bundle.report_template.name if bundle.report_template else None,
            },
            "schedule": {
                "included": bundle.schedule is not None,
                "cron": bundle.schedule.cron if bundle.schedule else None,
            },
        }
