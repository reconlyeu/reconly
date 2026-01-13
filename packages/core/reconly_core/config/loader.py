"""YAML configuration loader for sources."""
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    """Configuration for a single source."""

    name: str
    type: str  # rss, website, youtube
    url: str
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    language: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'SourceConfig':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            type=data.get('type', 'rss'),
            url=data['url'],
            tags=data.get('tags', []),
            enabled=data.get('enabled', True),
            language=data.get('language'),
            provider=data.get('provider'),
            model=data.get('model')
        )


@dataclass
class DigestConfig:
    """Full configuration for digest system."""

    sources: List[SourceConfig] = field(default_factory=list)
    settings: Dict = field(default_factory=dict)

    @property
    def enabled_sources(self) -> List[SourceConfig]:
        """Get only enabled sources."""
        return [s for s in self.sources if s.enabled]

    def get_sources_by_tag(self, tags: List[str]) -> List[SourceConfig]:
        """Get sources filtered by tags."""
        if not tags:
            return self.enabled_sources

        return [
            s for s in self.enabled_sources
            if any(tag in s.tags for tag in tags)
        ]

    def get_sources_by_type(self, source_type: str) -> List[SourceConfig]:
        """Get sources filtered by type."""
        return [
            s for s in self.enabled_sources
            if s.type == source_type
        ]


def load_config(config_path: str = None) -> DigestConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file (default: config/sources.yaml)

    Returns:
        DigestConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if config_path is None:
        # Default to config/sources.yaml in project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'sources.yaml'

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data:
        return DigestConfig()

    # Parse sources
    sources = []
    for source_data in data.get('sources', []):
        try:
            sources.append(SourceConfig.from_dict(source_data))
        except Exception as e:
            print(f"Warning: Failed to parse source: {e}")
            continue

    # Parse settings
    settings = data.get('settings', {})

    return DigestConfig(sources=sources, settings=settings)


def create_default_config(config_path: str = None) -> str:
    """
    Create a default configuration file.

    Args:
        config_path: Path where to create config (default: config/sources.yaml)

    Returns:
        Path to created config file
    """
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'sources.yaml'

    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_config = """# Reconly Sources Configuration

sources:
  # RSS Feed Example
  - name: "Hacker News"
    type: rss
    url: https://news.ycombinator.com/rss
    tags:
      - tech
      - news
    enabled: true

  # Another RSS Feed
  - name: "Example Blog"
    type: rss
    url: https://example.com/feed.xml
    tags:
      - example
    enabled: false  # Disabled by default

  # Website Example (single page)
  - name: "Example Article"
    type: website
    url: https://example.com/article
    tags:
      - example
    enabled: false

# Global Settings
settings:
  # Default language for summaries
  language: de

  # Default provider and model
  provider: huggingface
  model: llama-3.3-70b

  # Auto-save to database
  auto_save: true

  # Database settings (PostgreSQL required)
  database:
    url: postgresql://reconly:reconly@localhost:5432/reconly

  # Batch processing settings
  batch:
    max_concurrent: 3  # Process max 3 sources at once
    delay_between: 2   # Delay in seconds between requests

  # Email settings (for future use)
  email:
    enabled: false
    recipients:
      - your@email.com
    schedule: "0 8 * * *"  # Cron format: Every day at 8 AM
"""

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(default_config)

    return str(config_path)
