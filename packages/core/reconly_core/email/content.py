"""Email content extraction utilities.

This module provides functions for extracting and cleaning email content,
particularly converting HTML emails to plain text while preserving links.
"""
import re
from typing import Optional

import html2text


def extract_email_content(
    html_content: str,
    preserve_links: bool = True,
    body_width: int = 0,
) -> str:
    """Extract plain text content from HTML email.

    Converts HTML to markdown-style plain text, preserving links and
    removing tracking pixels, scripts, and other non-content elements.

    Args:
        html_content: Raw HTML content from email
        preserve_links: Whether to preserve links in markdown format
        body_width: Line wrap width (0 for no wrapping)

    Returns:
        Clean plain text content

    Example:
        >>> html = '<p>Hello <a href="https://example.com">world</a></p>'
        >>> extract_email_content(html)
        'Hello [world](https://example.com)'
    """
    if not html_content:
        return ""

    # Pre-process: remove tracking pixels, scripts, and style tags
    html_content = _remove_tracking_elements(html_content)

    # Configure html2text
    h = html2text.HTML2Text()

    # Preserve links as markdown
    h.ignore_links = not preserve_links
    h.inline_links = True  # Use inline links [text](url) instead of reference style

    # Don't wrap lines (let the display handle it)
    h.body_width = body_width

    # Ignore images (including tracking pixels)
    h.ignore_images = True

    # Ignore emphasis to keep text cleaner
    h.ignore_emphasis = False

    # Skip internal links (anchors)
    h.skip_internal_links = True

    # Don't add extra line breaks
    h.single_line_break = True

    # Convert to text
    text = h.handle(html_content)

    # Post-process the text
    text = _clean_text(text)

    return text.strip()


def _remove_tracking_elements(html: str) -> str:
    """Remove tracking pixels, scripts, and other non-content elements.

    Args:
        html: Raw HTML content

    Returns:
        Cleaned HTML
    """
    # Remove script tags and their content
    html = re.sub(
        r"<script[^>]*>.*?</script>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove style tags and their content
    html = re.sub(
        r"<style[^>]*>.*?</style>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove noscript tags and their content
    html = re.sub(
        r"<noscript[^>]*>.*?</noscript>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove tracking pixels (1x1 images, common tracking domains)
    # Match img tags with width=1 or height=1 or both
    html = re.sub(
        r'<img[^>]*(?:width\s*=\s*["\']?1["\']?|height\s*=\s*["\']?1["\']?)[^>]*>',
        "",
        html,
        flags=re.IGNORECASE
    )

    # Remove images from common tracking domains
    tracking_domains = [
        r"(?:mail)?track",
        r"pixel",
        r"beacon",
        r"analytics",
        r"tracking",
        r"open\..*\.com",
        r"click\..*\.com",
    ]
    tracking_pattern = "|".join(tracking_domains)
    html = re.sub(
        rf'<img[^>]*src\s*=\s*["\'][^"\']*(?:{tracking_pattern})[^"\']*["\'][^>]*>',
        "",
        html,
        flags=re.IGNORECASE
    )

    # Remove hidden elements (display:none, visibility:hidden)
    html = re.sub(
        r'<[^>]*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^>]*>.*?</[^>]+>',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    return html


def _clean_text(text: str) -> str:
    """Clean up extracted text.

    Args:
        text: Extracted text

    Returns:
        Cleaned text
    """
    # Remove multiple consecutive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Remove lines that are just dashes or underscores (separators)
    text = re.sub(r"^[-_=]{3,}$", "", text, flags=re.MULTILINE)

    # Remove multiple spaces
    text = re.sub(r"  +", " ", text)

    # Remove common email footer patterns
    text = _remove_email_footers(text)

    return text


def _remove_email_footers(text: str) -> str:
    """Remove common email footer patterns.

    Args:
        text: Email text content

    Returns:
        Text with footers removed
    """
    # Common unsubscribe patterns - keep content before them
    footer_patterns = [
        # Unsubscribe links
        r"\n.*unsubscribe.*\n?$",
        r"\n.*opt[- ]?out.*\n?$",
        r"\n.*email preferences.*\n?$",
        r"\n.*manage.*subscription.*\n?$",
        # Privacy/legal
        r"\n.*this email was sent.*\n?$",
        r"\n.*you are receiving this.*\n?$",
        r"\n.*sent to.*@.*\n?$",
        # Address footers
        r"\n.*\d{5}(?:-\d{4})?.*\n?$",  # US ZIP code pattern
    ]

    for pattern in footer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    return text


def extract_text_from_multipart(
    text_part: Optional[str],
    html_part: Optional[str],
) -> str:
    """Extract text content from multipart email.

    Prefers plain text if available, falls back to converting HTML.

    Args:
        text_part: Plain text part of email (if available)
        html_part: HTML part of email (if available)

    Returns:
        Extracted text content
    """
    # Prefer plain text
    if text_part and text_part.strip():
        return text_part.strip()

    # Fall back to HTML conversion
    if html_part:
        return extract_email_content(html_part)

    return ""
