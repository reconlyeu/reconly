/**
 * Format a duration in seconds to a human-readable string.
 * Examples: "45s", "2m 30s", "-"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

/**
 * Format a token count to a human-readable string.
 * Examples: "500", "1.5K", "2.30M"
 */
export function formatTokens(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(2)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toLocaleString();
}

/**
 * Format total tokens from input/output counts.
 */
export function formatTokensTotal(tokensIn: number, tokensOut: number): string {
  return formatTokens(tokensIn + tokensOut);
}
