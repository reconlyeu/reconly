"""Bundle validation for feed marketplace.

Validates feed bundles against the JSON schema and additional business rules.
"""
from dataclasses import dataclass, field
import re


@dataclass
class ValidationResult:
    """Result of bundle validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


class BundleValidator:
    """Validates feed bundles against schema and business rules."""

    # Valid source types
    VALID_SOURCE_TYPES = {"rss", "youtube", "website", "blog", "podcast"}

    # Valid categories
    VALID_CATEGORIES = {"news", "finance", "tech", "science", "entertainment", "sports", "business", "other"}

    # Valid report formats
    VALID_REPORT_FORMATS = {"markdown", "html", "text"}

    # Valid filter modes
    VALID_FILTER_MODES = {"title_only", "content", "both"}

    # Valid digest modes
    VALID_DIGEST_MODES = {"individual", "per_source", "all_sources"}

    # Regex patterns
    SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")
    SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
    LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}$")

    def validate(self, data: dict) -> ValidationResult:
        """Validate a bundle dictionary.

        Args:
            data: Raw bundle data (parsed JSON)

        Returns:
            ValidationResult with is_valid flag and any errors/warnings
        """
        result = ValidationResult(is_valid=True)

        # Check schema version
        self._validate_schema_version(data, result)

        # Check bundle presence
        if "bundle" not in data:
            result.add_error("Missing required field: bundle")
            return result

        bundle = data["bundle"]

        # Validate required fields
        self._validate_required_fields(bundle, result)

        # Validate field formats
        self._validate_id(bundle, result)
        self._validate_version(bundle, result)
        self._validate_name(bundle, result)
        self._validate_description(bundle, result)
        self._validate_language(bundle, result)
        self._validate_category(bundle, result)
        self._validate_tags(bundle, result)

        # Validate sources
        self._validate_sources(bundle, result)

        # Validate optional templates
        self._validate_prompt_template(bundle, result)
        self._validate_report_template(bundle, result)

        # Validate schedule
        self._validate_schedule(bundle, result)

        # Validate output config
        self._validate_output_config(bundle, result)

        # Validate digest mode
        self._validate_digest_mode(bundle, result)

        # Validate compatibility section (top-level)
        self._validate_compatibility(data, result)

        # Validate metadata section (top-level)
        self._validate_metadata(data, result)

        # Validate author
        self._validate_author(bundle, result)

        return result

    def _validate_schema_version(self, data: dict, result: ValidationResult) -> None:
        """Validate schema_version field."""
        if "schema_version" not in data:
            result.add_error("Missing required field: schema_version")
            return

        version = data["schema_version"]
        if version != "1.0":
            result.add_error(f"Unsupported schema version: {version}. Expected: 1.0")

    def _validate_required_fields(self, bundle: dict, result: ValidationResult) -> None:
        """Validate presence of required bundle fields."""
        required = ["id", "name", "version", "sources"]
        for field_name in required:
            if field_name not in bundle:
                result.add_error(f"Missing required field: bundle.{field_name}")

    def _validate_id(self, bundle: dict, result: ValidationResult) -> None:
        """Validate bundle ID (slug format)."""
        if "id" not in bundle:
            return

        bundle_id = bundle["id"]
        if not isinstance(bundle_id, str):
            result.add_error("bundle.id must be a string")
            return

        if not self.SLUG_PATTERN.match(bundle_id):
            result.add_error(
                f"bundle.id must be kebab-case (lowercase letters, numbers, hyphens): {bundle_id}"
            )

    def _validate_version(self, bundle: dict, result: ValidationResult) -> None:
        """Validate semantic version."""
        if "version" not in bundle:
            return

        version = bundle["version"]
        if not isinstance(version, str):
            result.add_error("bundle.version must be a string")
            return

        if not self.SEMVER_PATTERN.match(version):
            result.add_error(
                f"bundle.version must be semantic version (X.Y.Z): {version}"
            )

    def _validate_name(self, bundle: dict, result: ValidationResult) -> None:
        """Validate bundle name."""
        if "name" not in bundle:
            return

        name = bundle["name"]
        if not isinstance(name, str):
            result.add_error("bundle.name must be a string")
            return

        if len(name) < 1:
            result.add_error("bundle.name cannot be empty")
        elif len(name) > 255:
            result.add_error("bundle.name exceeds maximum length of 255 characters")

    def _validate_description(self, bundle: dict, result: ValidationResult) -> None:
        """Validate bundle description."""
        if "description" not in bundle:
            return

        desc = bundle["description"]
        if not isinstance(desc, str):
            result.add_error("bundle.description must be a string")
            return

        if len(desc) > 2000:
            result.add_error("bundle.description exceeds maximum length of 2000 characters")

    def _validate_language(self, bundle: dict, result: ValidationResult) -> None:
        """Validate language code."""
        if "language" not in bundle:
            return

        lang = bundle["language"]
        if not isinstance(lang, str):
            result.add_error("bundle.language must be a string")
            return

        if not self.LANGUAGE_PATTERN.match(lang):
            result.add_error(
                f"bundle.language must be 2-letter ISO code: {lang}"
            )

    def _validate_category(self, bundle: dict, result: ValidationResult) -> None:
        """Validate bundle category."""
        if "category" not in bundle:
            return

        category = bundle["category"]
        if not isinstance(category, str):
            result.add_error("bundle.category must be a string")
            return

        if category not in self.VALID_CATEGORIES:
            result.add_error(
                f"Invalid category: {category}. "
                f"Valid options: {', '.join(sorted(self.VALID_CATEGORIES))}"
            )

    def _validate_tags(self, bundle: dict, result: ValidationResult) -> None:
        """Validate bundle tags."""
        if "tags" not in bundle:
            return

        tags = bundle["tags"]
        if not isinstance(tags, list):
            result.add_error("bundle.tags must be an array")
            return

        if len(tags) > 10:
            result.add_error("bundle.tags exceeds maximum of 10 tags")

        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                result.add_error(f"bundle.tags[{i}] must be a string")

    def _validate_sources(self, bundle: dict, result: ValidationResult) -> None:
        """Validate sources array."""
        if "sources" not in bundle:
            return

        sources = bundle["sources"]
        if not isinstance(sources, list):
            result.add_error("bundle.sources must be an array")
            return

        if len(sources) < 1:
            result.add_error("bundle.sources must have at least one source")
            return

        for i, source in enumerate(sources):
            self._validate_source(source, i, result)

    def _validate_source(self, source: dict, index: int, result: ValidationResult) -> None:
        """Validate a single source entry."""
        prefix = f"bundle.sources[{index}]"

        if not isinstance(source, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Required fields
        for field_name in ["name", "type", "url"]:
            if field_name not in source:
                result.add_error(f"{prefix}.{field_name} is required")

        # Validate name
        if "name" in source:
            name = source["name"]
            if not isinstance(name, str):
                result.add_error(f"{prefix}.name must be a string")
            elif len(name) < 1 or len(name) > 255:
                result.add_error(f"{prefix}.name must be 1-255 characters")

        # Validate type
        if "type" in source:
            source_type = source["type"]
            if not isinstance(source_type, str):
                result.add_error(f"{prefix}.type must be a string")
            elif source_type not in self.VALID_SOURCE_TYPES:
                result.add_error(
                    f"{prefix}.type invalid: {source_type}. "
                    f"Valid options: {', '.join(sorted(self.VALID_SOURCE_TYPES))}"
                )

        # Validate URL
        if "url" in source:
            url = source["url"]
            if not isinstance(url, str):
                result.add_error(f"{prefix}.url must be a string")
            elif not url.startswith(("http://", "https://")):
                result.add_warning(f"{prefix}.url should start with http:// or https://")

        # Validate optional filter_mode
        if "filter_mode" in source:
            mode = source["filter_mode"]
            if mode not in self.VALID_FILTER_MODES:
                result.add_error(
                    f"{prefix}.filter_mode invalid: {mode}. "
                    f"Valid options: {', '.join(sorted(self.VALID_FILTER_MODES))}"
                )

        # Validate optional keyword arrays
        for kw_field in ["include_keywords", "exclude_keywords"]:
            if kw_field in source:
                keywords = source[kw_field]
                if not isinstance(keywords, list):
                    result.add_error(f"{prefix}.{kw_field} must be an array")
                else:
                    for j, kw in enumerate(keywords):
                        if not isinstance(kw, str):
                            result.add_error(f"{prefix}.{kw_field}[{j}] must be a string")

    def _validate_prompt_template(self, bundle: dict, result: ValidationResult) -> None:
        """Validate prompt_template if present."""
        if "prompt_template" not in bundle:
            return

        template = bundle["prompt_template"]
        prefix = "bundle.prompt_template"

        if not isinstance(template, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Required fields
        for field_name in ["name", "system_prompt", "user_prompt_template"]:
            if field_name not in template:
                result.add_error(f"{prefix}.{field_name} is required")
            elif not isinstance(template[field_name], str):
                result.add_error(f"{prefix}.{field_name} must be a string")

        # Validate target_length
        if "target_length" in template:
            length = template["target_length"]
            if not isinstance(length, int):
                result.add_error(f"{prefix}.target_length must be an integer")
            elif length < 10 or length > 2000:
                result.add_error(f"{prefix}.target_length must be between 10 and 2000")

    def _validate_report_template(self, bundle: dict, result: ValidationResult) -> None:
        """Validate report_template if present."""
        if "report_template" not in bundle:
            return

        template = bundle["report_template"]
        prefix = "bundle.report_template"

        if not isinstance(template, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Required fields
        for field_name in ["name", "format", "template_content"]:
            if field_name not in template:
                result.add_error(f"{prefix}.{field_name} is required")

        # Validate format
        if "format" in template:
            fmt = template["format"]
            if fmt not in self.VALID_REPORT_FORMATS:
                result.add_error(
                    f"{prefix}.format invalid: {fmt}. "
                    f"Valid options: {', '.join(sorted(self.VALID_REPORT_FORMATS))}"
                )

    def _validate_schedule(self, bundle: dict, result: ValidationResult) -> None:
        """Validate schedule if present."""
        if "schedule" not in bundle:
            return

        schedule = bundle["schedule"]
        prefix = "bundle.schedule"

        if not isinstance(schedule, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Cron expression is optional but should be valid if present
        if "cron" in schedule:
            cron = schedule["cron"]
            if not isinstance(cron, str):
                result.add_error(f"{prefix}.cron must be a string")
            else:
                # Basic cron validation (5 parts)
                parts = cron.split()
                if len(parts) != 5:
                    result.add_warning(
                        f"{prefix}.cron should have 5 parts (minute hour day month weekday)"
                    )

    def _validate_output_config(self, bundle: dict, result: ValidationResult) -> None:
        """Validate output_config if present."""
        if "output_config" not in bundle:
            return

        config = bundle["output_config"]
        prefix = "bundle.output_config"

        if not isinstance(config, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Validate email config if present
        if "email" in config:
            email = config["email"]
            if not isinstance(email, dict):
                result.add_error(f"{prefix}.email must be an object")

    def _validate_digest_mode(self, bundle: dict, result: ValidationResult) -> None:
        """Validate digest_mode if present."""
        if "digest_mode" not in bundle:
            return

        mode = bundle["digest_mode"]
        if mode not in self.VALID_DIGEST_MODES:
            result.add_error(
                f"bundle.digest_mode invalid: {mode}. "
                f"Valid options: {', '.join(sorted(self.VALID_DIGEST_MODES))}"
            )

    def _validate_compatibility(self, data: dict, result: ValidationResult) -> None:
        """Validate compatibility section if present."""
        if "compatibility" not in data:
            return

        compat = data["compatibility"]
        prefix = "compatibility"

        if not isinstance(compat, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Validate min_reconly_version
        if "min_reconly_version" in compat:
            version = compat["min_reconly_version"]
            if not isinstance(version, str):
                result.add_error(f"{prefix}.min_reconly_version must be a string")
            elif not self.SEMVER_PATTERN.match(version):
                result.add_error(
                    f"{prefix}.min_reconly_version must be semantic version: {version}"
                )

        # Validate required_features
        if "required_features" in compat:
            features = compat["required_features"]
            if not isinstance(features, list):
                result.add_error(f"{prefix}.required_features must be an array")

    def _validate_metadata(self, data: dict, result: ValidationResult) -> None:
        """Validate metadata section if present."""
        if "metadata" not in data:
            return

        meta = data["metadata"]
        prefix = "metadata"

        if not isinstance(meta, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Validate URL fields
        for field_name in ["homepage", "repository"]:
            if field_name in meta:
                url = meta[field_name]
                if not isinstance(url, str):
                    result.add_error(f"{prefix}.{field_name} must be a string")
                elif not url.startswith(("http://", "https://")):
                    result.add_warning(f"{prefix}.{field_name} should be a valid URL")

    def _validate_author(self, bundle: dict, result: ValidationResult) -> None:
        """Validate author if present."""
        if "author" not in bundle:
            return

        author = bundle["author"]
        prefix = "bundle.author"

        if not isinstance(author, dict):
            result.add_error(f"{prefix} must be an object")
            return

        # Name is required
        if "name" not in author:
            result.add_error(f"{prefix}.name is required")
        elif not isinstance(author["name"], str):
            result.add_error(f"{prefix}.name must be a string")
