"""Bundle dataclass for feed marketplace.

Defines the FeedBundle dataclass and related types for serialization.
"""
from dataclasses import dataclass, field
from typing import Optional
import re


def slugify(name: str) -> str:
    """Convert a name to a kebab-case slug.

    Examples:
        "AI News Daily" -> "ai-news-daily"
        "SAP Analyst Brief" -> "sap-analyst-brief"
    """
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove any characters that aren't alphanumeric or hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


@dataclass
class BundleAuthor:
    """Author information for a bundle."""
    name: str
    github: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> dict:
        result = {"name": self.name}
        if self.github:
            result["github"] = self.github
        if self.email:
            result["email"] = self.email
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleAuthor":
        return cls(
            name=data.get("name", "Anonymous"),
            github=data.get("github"),
            email=data.get("email"),
        )


@dataclass
class BundleSource:
    """Source configuration in a bundle."""
    name: str
    type: str  # rss, youtube, website, blog, podcast
    url: str
    config: Optional[dict] = None
    default_language: Optional[str] = None
    include_keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    filter_mode: Optional[str] = None  # title_only, content, both
    use_regex: bool = False

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "type": self.type,
            "url": self.url,
        }
        if self.config:
            result["config"] = self.config
        if self.default_language:
            result["default_language"] = self.default_language
        if self.include_keywords:
            result["include_keywords"] = self.include_keywords
        if self.exclude_keywords:
            result["exclude_keywords"] = self.exclude_keywords
        if self.filter_mode:
            result["filter_mode"] = self.filter_mode
        if self.use_regex:
            result["use_regex"] = self.use_regex
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleSource":
        return cls(
            name=data["name"],
            type=data["type"],
            url=data["url"],
            config=data.get("config"),
            default_language=data.get("default_language"),
            include_keywords=data.get("include_keywords"),
            exclude_keywords=data.get("exclude_keywords"),
            filter_mode=data.get("filter_mode"),
            use_regex=data.get("use_regex", False),
        )


@dataclass
class BundlePromptTemplate:
    """Prompt template configuration in a bundle."""
    name: str
    system_prompt: str
    user_prompt_template: str
    description: Optional[str] = None
    language: str = "en"
    target_length: int = 150

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "language": self.language,
            "target_length": self.target_length,
        }
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundlePromptTemplate":
        return cls(
            name=data["name"],
            system_prompt=data["system_prompt"],
            user_prompt_template=data["user_prompt_template"],
            description=data.get("description"),
            language=data.get("language", "en"),
            target_length=data.get("target_length", 150),
        )


@dataclass
class BundleReportTemplate:
    """Report template configuration in a bundle."""
    name: str
    format: str  # markdown, html, text
    template_content: str
    description: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "format": self.format,
            "template_content": self.template_content,
        }
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleReportTemplate":
        return cls(
            name=data["name"],
            format=data["format"],
            template_content=data["template_content"],
            description=data.get("description"),
        )


@dataclass
class BundleSchedule:
    """Schedule configuration in a bundle."""
    cron: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict:
        result = {}
        if self.cron:
            result["cron"] = self.cron
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleSchedule":
        return cls(
            cron=data.get("cron"),
            description=data.get("description"),
        )


@dataclass
class BundleCompatibility:
    """Compatibility requirements for a bundle."""
    min_reconly_version: Optional[str] = None
    required_features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {}
        if self.min_reconly_version:
            result["min_reconly_version"] = self.min_reconly_version
        if self.required_features:
            result["required_features"] = self.required_features
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleCompatibility":
        return cls(
            min_reconly_version=data.get("min_reconly_version"),
            required_features=data.get("required_features", []),
        )


@dataclass
class BundleMetadata:
    """Metadata for a bundle."""
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None

    def to_dict(self) -> dict:
        result = {}
        if self.license:
            result["license"] = self.license
        if self.homepage:
            result["homepage"] = self.homepage
        if self.repository:
            result["repository"] = self.repository
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BundleMetadata":
        return cls(
            license=data.get("license"),
            homepage=data.get("homepage"),
            repository=data.get("repository"),
        )


@dataclass
class FeedBundle:
    """Complete feed bundle for export/import.

    A bundle contains everything needed to recreate a feed configuration:
    - Feed metadata (name, description, version)
    - Source configurations
    - Prompt template
    - Report template
    - Schedule configuration
    - Output configuration
    """
    # Required fields
    id: str  # slug identifier
    name: str
    version: str
    sources: list[BundleSource]

    # Optional fields
    description: Optional[str] = None
    author: Optional[BundleAuthor] = None
    category: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    language: Optional[str] = None
    prompt_template: Optional[BundlePromptTemplate] = None
    report_template: Optional[BundleReportTemplate] = None
    schedule: Optional[BundleSchedule] = None
    output_config: Optional[dict] = None
    digest_mode: str = "individual"
    compatibility: Optional[BundleCompatibility] = None
    metadata: Optional[BundleMetadata] = None

    @classmethod
    def from_feed_name(cls, name: str, **kwargs) -> "FeedBundle":
        """Create a bundle with auto-generated slug from feed name."""
        return cls(
            id=slugify(name),
            name=name,
            **kwargs,
        )

    def to_dict(self) -> dict:
        """Convert bundle to dictionary for JSON serialization."""
        bundle_data = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "sources": [s.to_dict() for s in self.sources],
        }

        if self.description:
            bundle_data["description"] = self.description
        if self.author:
            bundle_data["author"] = self.author.to_dict()
        if self.category:
            bundle_data["category"] = self.category
        if self.tags:
            bundle_data["tags"] = self.tags
        if self.language:
            bundle_data["language"] = self.language
        if self.prompt_template:
            bundle_data["prompt_template"] = self.prompt_template.to_dict()
        if self.report_template:
            bundle_data["report_template"] = self.report_template.to_dict()
        if self.schedule:
            bundle_data["schedule"] = self.schedule.to_dict()
        if self.output_config:
            bundle_data["output_config"] = self.output_config
        if self.digest_mode != "individual":
            bundle_data["digest_mode"] = self.digest_mode

        result = {
            "schema_version": "1.0",
            "bundle": bundle_data,
        }

        if self.compatibility:
            result["compatibility"] = self.compatibility.to_dict()
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "FeedBundle":
        """Create a bundle from dictionary (JSON deserialization)."""
        bundle_data = data.get("bundle", data)

        sources = [BundleSource.from_dict(s) for s in bundle_data["sources"]]

        prompt_template = None
        if "prompt_template" in bundle_data:
            prompt_template = BundlePromptTemplate.from_dict(bundle_data["prompt_template"])

        report_template = None
        if "report_template" in bundle_data:
            report_template = BundleReportTemplate.from_dict(bundle_data["report_template"])

        schedule = None
        if "schedule" in bundle_data:
            schedule = BundleSchedule.from_dict(bundle_data["schedule"])

        author = None
        if "author" in bundle_data:
            author = BundleAuthor.from_dict(bundle_data["author"])

        compatibility = None
        if "compatibility" in data:
            compatibility = BundleCompatibility.from_dict(data["compatibility"])

        metadata = None
        if "metadata" in data:
            metadata = BundleMetadata.from_dict(data["metadata"])

        return cls(
            id=bundle_data["id"],
            name=bundle_data["name"],
            version=bundle_data["version"],
            sources=sources,
            description=bundle_data.get("description"),
            author=author,
            category=bundle_data.get("category"),
            tags=bundle_data.get("tags", []),
            language=bundle_data.get("language"),
            prompt_template=prompt_template,
            report_template=report_template,
            schedule=schedule,
            output_config=bundle_data.get("output_config"),
            digest_mode=bundle_data.get("digest_mode", "individual"),
            compatibility=compatibility,
            metadata=metadata,
        )

    @property
    def provenance_string(self) -> str:
        """Get provenance string for imported templates (e.g., 'my-feed@1.0.0')."""
        return f"{self.id}@{self.version}"
