import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getAuthStatusConfig,
  needsReauthentication,
  handleReauthenticate,
  getReauthButtonText,
  getReauthButtonTitle,
} from '../useAuthStatus';
import type { Source, AuthStatus } from '@/types/entities';

// Mock the oauthApi
vi.mock('@/services/api', () => ({
  oauthApi: {
    getAuthorizationUrl: vi.fn(),
  },
}));

import { oauthApi } from '@/services/api';

describe('useAuthStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset window.location for tests
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });
  });

  describe('getAuthStatusConfig', () => {
    describe('full labels (default)', () => {
      it('returns correct config for "active" status', () => {
        const config = getAuthStatusConfig('active');

        expect(config).toEqual({
          label: 'Authenticated',
          bgColor: 'bg-status-success/10',
          textColor: 'text-status-success',
        });
      });

      it('returns correct config for "pending_oauth" status', () => {
        const config = getAuthStatusConfig('pending_oauth');

        expect(config).toEqual({
          label: 'Pending Auth',
          bgColor: 'bg-amber-500/10',
          textColor: 'text-amber-500',
        });
      });

      it('returns correct config for "auth_failed" status', () => {
        const config = getAuthStatusConfig('auth_failed');

        expect(config).toEqual({
          label: 'Auth Failed',
          bgColor: 'bg-status-failed/10',
          textColor: 'text-status-failed',
        });
      });
    });

    describe('compact labels', () => {
      it('returns compact config for "active" status', () => {
        const config = getAuthStatusConfig('active', true);

        expect(config).toEqual({
          label: 'Auth OK',
          bgColor: 'bg-status-success/10',
          textColor: 'text-status-success',
        });
      });

      it('returns compact config for "pending_oauth" status', () => {
        const config = getAuthStatusConfig('pending_oauth', true);

        expect(config).toEqual({
          label: 'Pending',
          bgColor: 'bg-amber-500/10',
          textColor: 'text-amber-500',
        });
      });

      it('returns compact config for "auth_failed" status', () => {
        const config = getAuthStatusConfig('auth_failed', true);

        expect(config).toEqual({
          label: 'Failed',
          bgColor: 'bg-status-failed/10',
          textColor: 'text-status-failed',
        });
      });
    });

    describe('edge cases', () => {
      it('returns null for null status', () => {
        const config = getAuthStatusConfig(null);
        expect(config).toBeNull();
      });

      it('returns null for undefined status', () => {
        const config = getAuthStatusConfig(undefined);
        expect(config).toBeNull();
      });
    });
  });

  describe('needsReauthentication', () => {
    it('returns false for non-IMAP sources', () => {
      const source: Source = {
        id: 1,
        name: 'RSS Feed',
        type: 'rss',
        url: 'https://example.com/feed.xml',
        enabled: true,
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };

      expect(needsReauthentication(source)).toBe(false);
    });

    it('returns false for IMAP source with active status', () => {
      const source: Source = {
        id: 1,
        name: 'Gmail',
        type: 'imap',
        enabled: true,
        auth_status: 'active',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'gmail' },
      };

      expect(needsReauthentication(source)).toBe(false);
    });

    it('returns true for IMAP source with pending_oauth status', () => {
      const source: Source = {
        id: 1,
        name: 'Gmail',
        type: 'imap',
        enabled: true,
        auth_status: 'pending_oauth',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'gmail' },
      };

      expect(needsReauthentication(source)).toBe(true);
    });

    it('returns true for IMAP source with auth_failed status', () => {
      const source: Source = {
        id: 1,
        name: 'Gmail',
        type: 'imap',
        enabled: true,
        auth_status: 'auth_failed',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'gmail' },
      };

      expect(needsReauthentication(source)).toBe(true);
    });

    it('returns false for IMAP source with null auth_status', () => {
      const source: Source = {
        id: 1,
        name: 'Generic IMAP',
        type: 'imap',
        enabled: true,
        auth_status: null as any,
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };

      expect(needsReauthentication(source)).toBe(false);
    });
  });

  describe('handleReauthenticate', () => {
    it('returns false for non-IMAP sources', async () => {
      const source: Source = {
        id: 1,
        name: 'RSS Feed',
        type: 'rss',
        url: 'https://example.com/feed.xml',
        enabled: true,
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };

      const result = await handleReauthenticate(source);
      expect(result).toBe(false);
    });

    it('redirects to OAuth URL for Gmail provider', async () => {
      const source: Source = {
        id: 1,
        name: 'Gmail',
        type: 'imap',
        enabled: true,
        auth_status: 'pending_oauth',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'gmail' },
      };

      vi.mocked(oauthApi.getAuthorizationUrl).mockResolvedValue({
        authorization_url: 'https://accounts.google.com/oauth',
      });

      const result = await handleReauthenticate(source);

      expect(result).toBe(true);
      expect(oauthApi.getAuthorizationUrl).toHaveBeenCalledWith('gmail', 1);
      expect(window.location.href).toBe('https://accounts.google.com/oauth');
    });

    it('redirects to OAuth URL for Outlook provider', async () => {
      const source: Source = {
        id: 1,
        name: 'Outlook',
        type: 'imap',
        enabled: true,
        auth_status: 'auth_failed',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'outlook' },
      };

      vi.mocked(oauthApi.getAuthorizationUrl).mockResolvedValue({
        authorization_url: 'https://login.microsoftonline.com/oauth',
      });

      const result = await handleReauthenticate(source);

      expect(result).toBe(true);
      expect(oauthApi.getAuthorizationUrl).toHaveBeenCalledWith('outlook', 1);
    });

    it('returns false for generic IMAP provider', async () => {
      const source: Source = {
        id: 1,
        name: 'Custom IMAP',
        type: 'imap',
        enabled: true,
        auth_status: 'auth_failed',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'generic' },
      };

      const result = await handleReauthenticate(source);

      expect(result).toBe(false);
      expect(oauthApi.getAuthorizationUrl).not.toHaveBeenCalled();
    });

    it('returns false when OAuth URL fetch fails', async () => {
      const source: Source = {
        id: 1,
        name: 'Gmail',
        type: 'imap',
        enabled: true,
        auth_status: 'pending_oauth',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
        config: { provider: 'gmail' },
      };

      vi.mocked(oauthApi.getAuthorizationUrl).mockRejectedValue(new Error('Network error'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const result = await handleReauthenticate(source);

      expect(result).toBe(false);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('getReauthButtonText', () => {
    it('returns "Authenticate" for pending_oauth status', () => {
      expect(getReauthButtonText('pending_oauth')).toBe('Authenticate');
    });

    it('returns "Re-auth" for auth_failed status', () => {
      expect(getReauthButtonText('auth_failed')).toBe('Re-auth');
    });

    it('returns "Re-auth" for active status', () => {
      expect(getReauthButtonText('active')).toBe('Re-auth');
    });

    it('returns "Re-auth" for null status', () => {
      expect(getReauthButtonText(null)).toBe('Re-auth');
    });

    it('returns "Re-auth" for undefined status', () => {
      expect(getReauthButtonText(undefined)).toBe('Re-auth');
    });
  });

  describe('getReauthButtonTitle', () => {
    it('returns "Complete authentication" for pending_oauth status', () => {
      expect(getReauthButtonTitle('pending_oauth')).toBe('Complete authentication');
    });

    it('returns "Re-authenticate" for auth_failed status', () => {
      expect(getReauthButtonTitle('auth_failed')).toBe('Re-authenticate');
    });

    it('returns "Re-authenticate" for active status', () => {
      expect(getReauthButtonTitle('active')).toBe('Re-authenticate');
    });

    it('returns "Re-authenticate" for null status', () => {
      expect(getReauthButtonTitle(null)).toBe('Re-authenticate');
    });
  });
});
