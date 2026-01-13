/**
 * Edition-aware feature flags for Skimberry UI.
 *
 * Features are controlled by the VITE_EDITION environment variable:
 * - 'oss' (default): Open source edition, cost features disabled
 * - 'enterprise': Enterprise edition, all features enabled
 *
 * Usage in Vue components:
 * ```vue
 * <script setup lang="ts">
 * import { features } from '@/config/features'
 * </script>
 *
 * <template>
 *   <div v-if="features.costDisplay">
 *     <p>Cost: {{ cost }}</p>
 *   </div>
 * </template>
 * ```
 *
 * Usage in composables:
 * ```ts
 * import { features } from '@/config/features'
 *
 * if (features.costTracking) {
 *   trackCost(amount)
 * }
 * ```
 */

export type Edition = 'oss' | 'enterprise';

/**
 * Get the current edition from environment variable.
 * Defaults to 'oss' if not set or invalid.
 */
export function getEdition(): Edition {
  const edition = import.meta.env.VITE_EDITION?.toLowerCase();

  if (edition === 'enterprise') {
    return 'enterprise';
  }

  return 'oss';
}

/**
 * Check if running in enterprise mode.
 */
export function isEnterprise(): boolean {
  return getEdition() === 'enterprise';
}

/**
 * Check if running in OSS mode.
 */
export function isOss(): boolean {
  return getEdition() === 'oss';
}

/**
 * Feature flags based on edition.
 *
 * These flags control which features are available in the UI.
 * In OSS edition, cost-related features are disabled.
 * In Enterprise edition, all features are enabled.
 */
export const features = {
  /**
   * Whether cost tracking is enabled.
   * Enterprise only - OSS users bring their own API keys.
   */
  get costTracking(): boolean {
    return isEnterprise();
  },

  /**
   * Whether to display cost information in the UI.
   * Enterprise only - OSS doesn't track costs.
   */
  get costDisplay(): boolean {
    return isEnterprise();
  },

  /**
   * Whether billing features are enabled.
   * Enterprise only - OSS has no billing.
   */
  get billing(): boolean {
    return isEnterprise();
  },

  /**
   * Whether usage limits are enforced.
   * Enterprise only - OSS has no usage limits.
   */
  get usageLimits(): boolean {
    return isEnterprise();
  },

  /**
   * Whether multi-user features are enabled.
   * Enterprise only - OSS is single-user.
   */
  get multiUser(): boolean {
    return isEnterprise();
  },

  /**
   * Whether password authentication is available.
   * Available in both editions when configured.
   */
  get passwordAuth(): boolean {
    // Password auth is available in both editions
    return true;
  },
} as const;

/**
 * Current edition value.
 * Use this for direct edition checks or display purposes.
 */
export const EDITION: Edition = getEdition();
