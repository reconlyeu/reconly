"""Base metadata for all extensible components.

This module defines the base ComponentMetadata dataclass that all component-specific
metadata classes inherit from. It provides common fields and serialization methods
for providers, fetchers, and exporters.

Example:
    >>> from reconly_core.metadata import ComponentMetadata
    >>> metadata = ComponentMetadata(
    ...     name="my_component",
    ...     display_name="My Component",
    ...     description="A sample component",
    ... )
    >>> metadata.to_dict()
    {'name': 'my_component', 'display_name': 'My Component', 'description': 'A sample component', 'icon': None}
"""
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ComponentMetadata:
    """Base metadata for all extensible components.

    This dataclass provides common metadata fields that all component types
    (providers, fetchers, exporters) share. Component-specific metadata classes
    should inherit from this and add their own fields.

    Attributes:
        name: Internal identifier used in code and configuration (e.g., 'lmstudio', 'rss').
              Should be lowercase with underscores, no spaces.
        display_name: Human-readable name for UI display (e.g., 'LM Studio', 'RSS Feed').
        description: Short description of the component for tooltips and help text.
        icon: Icon identifier for UI rendering (e.g., 'mdi:rss', 'simple-icons:openai').
              Uses iconify format. None if no icon is defined.
    """

    name: str
    display_name: str
    description: str
    icon: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Returns:
            Dictionary with all metadata fields serialized.
            Subclasses should override this if they need custom serialization.

        Example:
            >>> metadata = ComponentMetadata(name="test", display_name="Test", description="A test")
            >>> metadata.to_dict()
            {'name': 'test', 'display_name': 'Test', 'description': 'A test', 'icon': None}
        """
        return asdict(self)
