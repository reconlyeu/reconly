/**
 * URL patterns for common badge/shield services that should be filtered out
 * from preview images (they're typically small, uninformative badges).
 */
const BADGE_URL_PATTERNS = [
  /shields\.io/i,
  /badgen\.net/i,
  /badge\.fury\.io/i,
  /travis-ci\.(org|com)/i,
  /circleci\.com/i,
  /codecov\.io/i,
  /coveralls\.io/i,
  /github\.com\/.*\/(badge|workflows)/i,
  /img\.shields\.io/i,
  /badge[s]?\./i,
  /\.svg(\?|$)/i, // Most badges are SVGs
  /camo\.githubusercontent\.com/i, // GitHub's image proxy often used for badges
];

/**
 * Check if a URL points to a badge/shield image
 */
export function isBadgeUrl(url: string): boolean {
  return BADGE_URL_PATTERNS.some((pattern) => pattern.test(url));
}

/**
 * Extract image URL from srcset attribute (takes the first/smallest image)
 */
function extractFromSrcset(srcset: string): string | null {
  // srcset format: "url1 640w, url2 1280w" or "url1 1x, url2 2x"
  const parts = srcset.split(',').map((s) => s.trim());
  for (const part of parts) {
    // Extract URL (everything before the optional size descriptor)
    const url = part.split(/\s+/)[0];
    if (url && !isBadgeUrl(url)) {
      return url;
    }
  }
  return null;
}

/**
 * Extract the first non-badge image URL from HTML content
 * Checks src, srcset, and data-src attributes in img tags,
 * and also handles orphaned srcset attributes (malformed HTML)
 */
export function extractPreviewImage(html: string): string | null {
  // Find all img tags
  const imgTagMatches = html.matchAll(/<img[^>]*>/gi);

  for (const tagMatch of imgTagMatches) {
    const imgTag = tagMatch[0];

    // Try src attribute first
    const srcMatch = imgTag.match(/\ssrc=["']([^"']+)["']/i);
    if (srcMatch && !isBadgeUrl(srcMatch[1])) {
      return srcMatch[1];
    }

    // Try srcset attribute (extract first URL)
    const srcsetMatch = imgTag.match(/\ssrcset=["']([^"']+)["']/i);
    if (srcsetMatch) {
      const srcsetUrl = extractFromSrcset(srcsetMatch[1]);
      if (srcsetUrl) {
        return srcsetUrl;
      }
    }

    // Try data-src (lazy loading)
    const dataSrcMatch = imgTag.match(/\sdata-src=["']([^"']+)["']/i);
    if (dataSrcMatch && !isBadgeUrl(dataSrcMatch[1])) {
      return dataSrcMatch[1];
    }
  }

  // Fallback: look for orphaned srcset attributes (malformed HTML)
  // Some sites have srcset= outside of <img> tags
  const orphanedSrcset = html.match(/\bsrcset=["']([^"']+)["']/i);
  if (orphanedSrcset) {
    const srcsetUrl = extractFromSrcset(orphanedSrcset[1]);
    if (srcsetUrl) {
      return srcsetUrl;
    }
  }

  return null;
}
