"""Image extraction utilities for preview thumbnails.

This module provides functions to extract preview images from HTML content
and URLs, prioritizing Open Graph images for better quality thumbnails.

The logic mirrors the frontend imageUtils.ts for consistency.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# URL patterns for badge/shield services that should be filtered out
# (typically small, uninformative images)
BADGE_URL_PATTERNS = [
    re.compile(r'shields\.io', re.IGNORECASE),
    re.compile(r'badgen\.net', re.IGNORECASE),
    re.compile(r'badge\.fury\.io', re.IGNORECASE),
    re.compile(r'travis-ci\.(org|com)', re.IGNORECASE),
    re.compile(r'circleci\.com', re.IGNORECASE),
    re.compile(r'codecov\.io', re.IGNORECASE),
    re.compile(r'coveralls\.io', re.IGNORECASE),
    re.compile(r'github\.com/.*/(?:badge|workflows)', re.IGNORECASE),
    re.compile(r'img\.shields\.io', re.IGNORECASE),
    re.compile(r'badges?\.', re.IGNORECASE),
    re.compile(r'\.svg(?:\?|$)', re.IGNORECASE),
    re.compile(r'camo\.githubusercontent\.com', re.IGNORECASE),
    # Common small/icon images
    re.compile(r'favicon', re.IGNORECASE),
    re.compile(r'logo.*\d+x\d+', re.IGNORECASE),  # logo-32x32.png etc.
    re.compile(r'icon.*\d+', re.IGNORECASE),
]

# Default headers for fetching URLs
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def is_badge_url(url: str) -> bool:
    """Check if a URL points to a badge/shield image that should be skipped."""
    return any(pattern.search(url) for pattern in BADGE_URL_PATTERNS)


def extract_og_image(html: str, base_url: Optional[str] = None) -> Optional[str]:
    """Extract Open Graph or Twitter image from HTML meta tags.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative image URLs

    Returns:
        Image URL if found, None otherwise
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Try og:image first (most common for social sharing)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content'].strip()
            if image_url and not is_badge_url(image_url):
                if base_url and not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(base_url, image_url)
                return image_url

        # Fallback to twitter:image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image['content'].strip()
            if image_url and not is_badge_url(image_url):
                if base_url and not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(base_url, image_url)
                return image_url

        # Also try twitter:image:src variant
        twitter_image_src = soup.find('meta', attrs={'name': 'twitter:image:src'})
        if twitter_image_src and twitter_image_src.get('content'):
            image_url = twitter_image_src['content'].strip()
            if image_url and not is_badge_url(image_url):
                if base_url and not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(base_url, image_url)
                return image_url

    except Exception as e:
        logger.debug("Failed to extract og:image", extra={"error": str(e)})

    return None


def extract_content_image(html: str, base_url: Optional[str] = None) -> Optional[str]:
    """Extract the first non-badge image from HTML content.

    Checks src, srcset, and data-src attributes in img tags.
    Mirrors the frontend imageUtils.ts logic.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative image URLs

    Returns:
        First valid image URL if found, None otherwise
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        for img in soup.find_all('img'):
            # Try src attribute first
            src = img.get('src', '').strip()
            if src and not is_badge_url(src):
                if base_url and not src.startswith(('http://', 'https://', 'data:')):
                    src = urljoin(base_url, src)
                if not src.startswith('data:'):  # Skip data URLs
                    return src

            # Try srcset attribute (take first URL)
            srcset = img.get('srcset', '').strip()
            if srcset:
                # srcset format: "url1 640w, url2 1280w"
                first_url = srcset.split(',')[0].split()[0].strip()
                if first_url and not is_badge_url(first_url):
                    if base_url and not first_url.startswith(('http://', 'https://')):
                        first_url = urljoin(base_url, first_url)
                    return first_url

            # Try data-src (lazy loading)
            data_src = img.get('data-src', '').strip()
            if data_src and not is_badge_url(data_src):
                if base_url and not data_src.startswith(('http://', 'https://')):
                    data_src = urljoin(base_url, data_src)
                return data_src

    except Exception as e:
        logger.debug("Failed to extract content image", extra={"error": str(e)})

    return None


def extract_preview_image(html: str, base_url: Optional[str] = None) -> Optional[str]:
    """Extract preview image from HTML, preferring og:image over content images.

    This is the main function to use for extracting preview thumbnails.
    It tries og:image/twitter:image first (better quality), then falls back
    to the first image in the content.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative image URLs

    Returns:
        Best available image URL, or None if no images found
    """
    # Try og:image first (higher quality, author-chosen)
    image_url = extract_og_image(html, base_url)
    if image_url:
        return image_url

    # Fall back to first content image
    return extract_content_image(html, base_url)


def fetch_og_image(url: str, timeout: int = 5) -> Optional[str]:
    """Fetch a URL and extract its og:image.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        og:image URL if found, None otherwise
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None

        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if response.status_code != 200:
            return None

        return extract_og_image(response.text, url)

    except Exception as e:
        logger.debug("Failed to fetch og:image", extra={"url": url, "error": str(e)})
        return None


def fetch_preview_image_from_urls(
    urls: list[str],
    max_attempts: int = 5,
    timeout: int = 5,
) -> Optional[str]:
    """Fetch og:image from a list of URLs, returning the first valid one.

    Used by agent fetcher to get preview images from research sources.

    Args:
        urls: List of URLs to try
        max_attempts: Maximum number of URLs to attempt
        timeout: Request timeout per URL in seconds

    Returns:
        First valid image URL found, or None
    """
    if not urls:
        return None

    for url in urls[:max_attempts]:
        image_url = fetch_og_image(url, timeout)
        if image_url:
            logger.info(
                "Preview image extracted from source",
                extra={"source_url": url, "image_url": image_url},
            )
            return image_url

    return None
