#!/usr/bin/env python3
"""Quick database query script for Reconly."""
import sys
import io

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from reconly_core.database import DigestDB

# Initialize database connection
db = DigestDB()

# Get all digests
digests = db.list_digests(limit=100)

print(f"Total digests: {len(digests)}\n")

for digest in digests[:10]:  # Show first 10
    print(f"ID: {digest.id}")
    print(f"Title: {digest.title}")
    print(f"Type: {digest.source_type}")
    print(f"URL: {digest.url}")
    print(f"Created: {digest.created_at}")
    print(f"User ID: {digest.user_id}")
    print(f"Tags: {[tag.tag.name for tag in digest.tags]}")
    print("-" * 80)

# Custom query example
print("\nYouTube videos only:")
youtube_digests = [d for d in digests if d.source_type == 'youtube']
for yt in youtube_digests:
    print(f"  - {yt.title} ({yt.url})")

# Search example
print("\nSearch for 'video':")
search_results = db.search_digests("video", limit=5)
for result in search_results:
    print(f"  - {result.title}")

# Stats
print("\nStats:")
print(f"  Total digests: {len(digests)}")
print(f"  YouTube videos: {len(youtube_digests)}")
print(f"  RSS articles: {len([d for d in digests if d.source_type == 'rss'])}")
total_cost = sum([d.estimated_cost for d in digests if d.estimated_cost])
print(f"  Total cost: ${total_cost:.4f}")
