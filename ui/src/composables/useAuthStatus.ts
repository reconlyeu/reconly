/**
 * Composable for IMAP source authentication status handling.
 * Provides auth status configuration and re-authentication logic.
 */
import { oauthApi } from '@/services/api';
import type { Source, AuthStatus } from '@/types/entities';

export interface AuthStatusDisplayConfig {
  label: string;
  bgColor: string;
  textColor: string;
}

const AUTH_STATUS_CONFIGS: Record<AuthStatus, AuthStatusDisplayConfig> = {
  active: {
    label: 'Authenticated',
    bgColor: 'bg-status-success/10',
    textColor: 'text-status-success',
  },
  pending_oauth: {
    label: 'Pending Auth',
    bgColor: 'bg-amber-500/10',
    textColor: 'text-amber-500',
  },
  auth_failed: {
    label: 'Auth Failed',
    bgColor: 'bg-status-failed/10',
    textColor: 'text-status-failed',
  },
};

// Shorter labels for compact displays (e.g., table cells)
const AUTH_STATUS_CONFIGS_COMPACT: Record<AuthStatus, AuthStatusDisplayConfig> = {
  active: {
    label: 'Auth OK',
    bgColor: 'bg-status-success/10',
    textColor: 'text-status-success',
  },
  pending_oauth: {
    label: 'Pending',
    bgColor: 'bg-amber-500/10',
    textColor: 'text-amber-500',
  },
  auth_failed: {
    label: 'Failed',
    bgColor: 'bg-status-failed/10',
    textColor: 'text-status-failed',
  },
};

/**
 * Get display configuration for an auth status.
 * @param status - The auth status to get config for
 * @param compact - Use shorter labels for compact displays
 */
export function getAuthStatusConfig(
  status: AuthStatus | null | undefined,
  compact = false
): AuthStatusDisplayConfig | null {
  if (!status) return null;
  const configs = compact ? AUTH_STATUS_CONFIGS_COMPACT : AUTH_STATUS_CONFIGS;
  return configs[status] ?? null;
}

/**
 * Check if a source needs re-authentication.
 */
export function needsReauthentication(source: Source): boolean {
  return (
    source.type === 'imap' &&
    source.auth_status !== undefined &&
    source.auth_status !== null &&
    source.auth_status !== 'active'
  );
}

/**
 * Handle re-authentication for an IMAP source.
 * For OAuth providers (gmail, outlook), redirects to the authorization URL.
 * For generic IMAP, returns false to indicate the caller should handle it differently.
 *
 * @param source - The source to re-authenticate
 * @returns True if OAuth redirect was initiated, false if generic IMAP
 */
export async function handleReauthenticate(source: Source): Promise<boolean> {
  if (source.type !== 'imap') return false;

  const provider = source.config?.provider;
  if (provider === 'gmail' || provider === 'outlook') {
    try {
      const response = await oauthApi.getAuthorizationUrl(provider, source.id);
      window.location.href = response.authorization_url;
      return true;
    } catch (error) {
      console.error('Failed to get OAuth URL:', error);
      return false;
    }
  }

  // Generic IMAP - caller should handle differently (e.g., open edit modal)
  return false;
}

/**
 * Get the button text for re-authentication based on auth status.
 */
export function getReauthButtonText(authStatus: AuthStatus | null | undefined): string {
  if (authStatus === 'pending_oauth') {
    return 'Authenticate';
  }
  return 'Re-auth';
}

/**
 * Get the tooltip text for re-authentication button.
 */
export function getReauthButtonTitle(authStatus: AuthStatus | null | undefined): string {
  if (authStatus === 'pending_oauth') {
    return 'Complete authentication';
  }
  return 'Re-authenticate';
}
