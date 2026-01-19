"""Tests for ContentFilter class."""
from reconly_core.services.content_filter import ContentFilter


class TestContentFilterKeywords:
    """Test keyword matching (non-regex mode)."""

    def test_no_filters_passes_all(self):
        """Content with no filters should pass all items."""
        filter = ContentFilter()
        assert filter.matches("Any Title", "Any content here")
        assert filter.matches("", "")

    def test_include_keywords_match(self):
        """Items must match at least one include keyword."""
        filter = ContentFilter(include_keywords=["python", "javascript"])

        assert filter.matches("Python Tutorial", "Learn programming")
        assert filter.matches("Web Dev", "Using javascript frameworks")
        assert not filter.matches("Ruby Guide", "Learn Ruby on Rails")

    def test_include_keywords_case_insensitive(self):
        """Keyword matching should be case-insensitive."""
        filter = ContentFilter(include_keywords=["SAP"])

        assert filter.matches("SAP Integration", "Content")
        assert filter.matches("sap integration", "content")
        assert filter.matches("New Sap Features", "content")

    def test_exclude_keywords_match(self):
        """Items matching exclude keywords should be rejected."""
        filter = ContentFilter(exclude_keywords=["sponsored", "advertisement"])

        assert filter.matches("Tech News", "Real content here")
        assert not filter.matches("Tech News", "This is a sponsored post")
        assert not filter.matches("Advertisement Alert", "Product info")

    def test_include_and_exclude_combined(self):
        """Both include and exclude filters must pass."""
        filter = ContentFilter(
            include_keywords=["cloud"],
            exclude_keywords=["sponsored"]
        )

        # Has cloud, no sponsored - passes
        assert filter.matches("Cloud Computing", "AWS services")

        # Has cloud AND sponsored - fails (exclude takes precedence)
        assert not filter.matches("Cloud News", "Sponsored by AWS")

        # No cloud - fails include check
        assert not filter.matches("On-premise", "Local servers")


class TestContentFilterMode:
    """Test filter mode (title_only, content, both)."""

    def test_title_only_mode(self):
        """Filter should only check title in title_only mode."""
        filter = ContentFilter(
            include_keywords=["python"],
            filter_mode="title_only"
        )

        # Keyword in title - passes
        assert filter.matches("Python Guide", "Content without keyword")

        # Keyword only in content - fails
        assert not filter.matches("Programming Guide", "Learn python here")

    def test_content_only_mode(self):
        """Filter should only check content in content mode."""
        filter = ContentFilter(
            include_keywords=["python"],
            filter_mode="content"
        )

        # Keyword only in title - fails
        assert not filter.matches("Python Guide", "No keyword in body")

        # Keyword in content - passes
        assert filter.matches("Guide", "Learn python programming")

    def test_both_mode(self):
        """Filter should check both title and content in both mode."""
        filter = ContentFilter(
            include_keywords=["python"],
            filter_mode="both"
        )

        # Keyword in title - passes
        assert filter.matches("Python Guide", "No keyword")

        # Keyword in content - passes
        assert filter.matches("Guide", "Learn python")

        # No keyword anywhere - fails
        assert not filter.matches("Guide", "Nothing here")


class TestContentFilterRegex:
    """Test regex pattern matching."""

    def test_regex_pattern_match(self):
        """Regex patterns should match correctly."""
        filter = ContentFilter(
            include_keywords=[r"python\s*3\.\d+"],
            use_regex=True
        )

        assert filter.matches("Python 3.11 Release", "content")
        assert filter.matches("title", "Using Python3.9 today")
        assert not filter.matches("Python 2.7 EOL", "content")

    def test_regex_exclude_pattern(self):
        """Regex exclude patterns should work."""
        filter = ContentFilter(
            exclude_keywords=[r"\[AD\]", r"sponsored"],
            use_regex=True
        )

        assert filter.matches("News Title", "Real content")
        assert not filter.matches("[AD] Product", "Buy now")
        assert not filter.matches("Title", "This is sponsored content")

    def test_regex_word_boundary(self):
        """Test word boundary patterns."""
        filter = ContentFilter(
            include_keywords=[r"\bapi\b"],
            use_regex=True
        )

        assert filter.matches("Using the API", "content")
        assert filter.matches("title", "REST api guide")
        assert not filter.matches("rapid development", "apikey usage")


class TestContentFilterValidation:
    """Test pattern validation."""

    def test_validate_valid_patterns(self):
        """Valid regex patterns should pass validation."""
        valid, error = ContentFilter.validate_patterns([r"\d+", r"[a-z]+"])
        assert valid is True
        assert error is None

    def test_validate_invalid_patterns(self):
        """Invalid regex patterns should fail validation."""
        valid, error = ContentFilter.validate_patterns([r"[invalid"])
        assert valid is False
        assert "Invalid regex pattern" in error

    def test_validate_empty_patterns(self):
        """Empty or None patterns should pass validation."""
        valid, error = ContentFilter.validate_patterns(None)
        assert valid is True

        valid, error = ContentFilter.validate_patterns([])
        assert valid is True

    def test_validate_mixed_patterns(self):
        """Mixed valid/invalid patterns should fail."""
        valid, error = ContentFilter.validate_patterns([r"\d+", r"(unclosed"])
        assert valid is False


class TestContentFilterEdgeCases:
    """Test edge cases and null handling."""

    def test_empty_title_and_content(self):
        """Empty strings should be handled gracefully."""
        filter = ContentFilter(include_keywords=["test"])

        assert not filter.matches("", "")
        assert not filter.matches(None, None)  # type: ignore
        assert filter.matches("test", None)  # type: ignore
        assert filter.matches(None, "test")  # type: ignore

    def test_empty_keywords_list(self):
        """Empty keyword lists should behave like no filter."""
        filter = ContentFilter(include_keywords=[], exclude_keywords=[])
        assert filter.matches("Any", "Content")

    def test_repr(self):
        """Test string representation."""
        filter = ContentFilter(
            include_keywords=["a"],
            exclude_keywords=["b"],
            filter_mode="title_only",
            use_regex=True
        )
        repr_str = repr(filter)
        assert "include=['a']" in repr_str
        assert "exclude=['b']" in repr_str
        assert "mode=title_only" in repr_str
        assert "regex=True" in repr_str
