"""Content filter for filtering fetched items before LLM summarization.

Filters items based on include/exclude keywords with optional regex support.
Designed to reduce noise and LLM costs by processing only relevant content.
"""
import re
from typing import Literal


FilterMode = Literal["title_only", "content", "both"]


class ContentFilter:
    """
    Filter content items based on keyword include/exclude rules.

    Logic:
    - If include_keywords set: item must match at least one keyword
    - If exclude_keywords set: item must NOT match any keyword
    - Both conditions must pass for item to be included
    """

    def __init__(
        self,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        filter_mode: FilterMode = "both",
        use_regex: bool = False,
    ):
        """
        Initialize content filter.

        Args:
            include_keywords: Keywords that must match (at least one). None = no include filter.
            exclude_keywords: Keywords that must NOT match (any). None = no exclude filter.
            filter_mode: Where to search - "title_only", "content", or "both" (default).
            use_regex: If True, interpret keywords as regex patterns.
        """
        self.include_keywords = include_keywords or []
        self.exclude_keywords = exclude_keywords or []
        self.filter_mode = filter_mode
        self.use_regex = use_regex

        # Pre-compile regex patterns if using regex mode
        if self.use_regex:
            self._include_patterns = [re.compile(k, re.IGNORECASE) for k in self.include_keywords]
            self._exclude_patterns = [re.compile(k, re.IGNORECASE) for k in self.exclude_keywords]
        else:
            self._include_patterns = []
            self._exclude_patterns = []

    def matches(self, title: str, content: str) -> bool:
        """
        Check if content matches the filter criteria.

        Args:
            title: Item title
            content: Item content body

        Returns:
            True if item passes all filter criteria, False if it should be excluded.
        """
        # Determine text to search based on filter_mode
        text_to_search = self._get_text_to_search(title, content)

        # Check include filter (if set, must match at least one)
        if self.include_keywords:
            if not self._matches_any(text_to_search, self.include_keywords, self._include_patterns):
                return False

        # Check exclude filter (if set, must NOT match any)
        if self.exclude_keywords:
            if self._matches_any(text_to_search, self.exclude_keywords, self._exclude_patterns):
                return False

        return True

    def _get_text_to_search(self, title: str, content: str) -> str:
        """Get the text to search based on filter_mode."""
        if self.filter_mode == "title_only":
            return title or ""
        elif self.filter_mode == "content":
            return content or ""
        else:  # "both" (default)
            return f"{title or ''} {content or ''}"

    def _matches_any(self, text: str, keywords: list[str], patterns: list[re.Pattern]) -> bool:
        """Check if text matches any of the keywords/patterns."""
        if self.use_regex:
            return any(pattern.search(text) for pattern in patterns)
        else:
            text_lower = text.lower()
            return any(keyword.lower() in text_lower for keyword in keywords)

    @staticmethod
    def validate_patterns(patterns: list[str] | None) -> tuple[bool, str | None]:
        """
        Validate that all patterns are valid regex.

        Args:
            patterns: List of regex pattern strings to validate.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        if not patterns:
            return True, None

        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                return False, f"Invalid regex pattern '{pattern}': {e}"

        return True, None

    def __repr__(self) -> str:
        return (
            f"ContentFilter(include={self.include_keywords}, "
            f"exclude={self.exclude_keywords}, "
            f"mode={self.filter_mode}, regex={self.use_regex})"
        )
