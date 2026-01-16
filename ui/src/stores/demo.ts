/**
 * Demo Mode Store
 *
 * Manages demo mode state for the application.
 * Fetches demo_mode status from the health endpoint and handles
 * banner dismissal state persisted in sessionStorage.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { healthApi } from '@/services/api';

const DISMISSED_KEY = 'reconly_demo_banner_dismissed';

export const useDemoStore = defineStore('demo', () => {
  // State
  const isDemoMode = ref(false);
  const isDismissed = ref(false);
  const isLoading = ref(true);
  const error = ref<string | null>(null);

  // Computed
  const showBanner = computed(() => isDemoMode.value && !isDismissed.value);

  /**
   * Initialize dismissed state from sessionStorage.
   */
  function initDismissedState(): void {
    if (typeof sessionStorage !== 'undefined') {
      isDismissed.value = sessionStorage.getItem(DISMISSED_KEY) === 'true';
    }
  }

  /**
   * Fetch demo mode status from the health endpoint.
   */
  async function fetchDemoMode(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const health = await healthApi.check();
      isDemoMode.value = health.demo_mode;
    } catch (err: any) {
      error.value = err.detail || 'Failed to fetch demo mode status';
      // Default to false on error
      isDemoMode.value = false;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Dismiss the demo banner and persist to sessionStorage.
   */
  function dismissBanner(): void {
    isDismissed.value = true;
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(DISMISSED_KEY, 'true');
    }
  }

  /**
   * Reset dismissed state (for testing or re-showing banner).
   */
  function resetDismissed(): void {
    isDismissed.value = false;
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem(DISMISSED_KEY);
    }
  }

  // Initialize dismissed state on store creation
  initDismissedState();

  return {
    // State
    isDemoMode,
    isDismissed,
    isLoading,
    error,

    // Computed
    showBanner,

    // Actions
    fetchDemoMode,
    dismissBanner,
    resetDismissed,
  };
});
