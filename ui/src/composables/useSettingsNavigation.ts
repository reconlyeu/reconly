/**
 * Shared state for navigating between Settings tabs with a target item.
 * Used for deep-linking from Extensions to Exporters/Fetchers without URL params.
 */
import { ref } from 'vue';

export type SettingsTab = 'providers' | 'email' | 'exports' | 'fetchers' | 'extensions' | 'agent';

interface NavigationTarget {
  tab: SettingsTab;
  exporter?: string;
  fetcher?: string;
}

// Shared state (singleton pattern - same instance across all imports)
const pendingNavigation = ref<NavigationTarget | null>(null);

export function useSettingsNavigation() {
  /**
   * Navigate to a tab with an optional target item.
   * Call this from ExtensionCard when clicking Configure.
   */
  const navigateTo = (target: NavigationTarget) => {
    pendingNavigation.value = target;
  };

  /**
   * Get and consume the pending navigation target.
   * Returns null if no pending navigation.
   */
  const consumeNavigation = (): NavigationTarget | null => {
    const target = pendingNavigation.value;
    pendingNavigation.value = null;
    return target;
  };

  /**
   * Check if there's a pending navigation without consuming it.
   */
  const hasPendingNavigation = () => pendingNavigation.value !== null;

  /**
   * Get the pending target for a specific type (exporter/fetcher).
   * Consumes the value after reading.
   */
  const consumeExporterTarget = (): string | null => {
    if (pendingNavigation.value?.exporter) {
      const target = pendingNavigation.value.exporter;
      pendingNavigation.value = null;
      return target;
    }
    return null;
  };

  const consumeFetcherTarget = (): string | null => {
    if (pendingNavigation.value?.fetcher) {
      const target = pendingNavigation.value.fetcher;
      pendingNavigation.value = null;
      return target;
    }
    return null;
  };

  return {
    pendingNavigation,
    navigateTo,
    consumeNavigation,
    hasPendingNavigation,
    consumeExporterTarget,
    consumeFetcherTarget,
  };
}
