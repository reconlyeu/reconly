/**
 * Composable for managing view mode (card vs table) per page.
 * Persists preference to localStorage.
 */
import { ref, computed, watch } from 'vue';

export type ViewMode = 'card' | 'table';

const STORAGE_KEY_PREFIX = 'reconly:viewMode:';

/**
 * Create a view mode composable for a specific page.
 * @param pageKey - Unique identifier for the page (e.g., 'digests', 'sources')
 * @param defaultMode - Default view mode if none is saved
 */
export function useViewMode(pageKey: string, defaultMode: ViewMode = 'card') {
  // Get stored value or use default
  const getStoredMode = (): ViewMode => {
    if (typeof window === 'undefined') return defaultMode;
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${pageKey}`);
    if (stored === 'card' || stored === 'table') {
      return stored;
    }
    return defaultMode;
  };

  const viewMode = ref<ViewMode>(getStoredMode());

  // Persist to localStorage when changed
  watch(viewMode, (newMode) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(`${STORAGE_KEY_PREFIX}${pageKey}`, newMode);
    }
  });

  const setViewMode = (mode: ViewMode) => {
    viewMode.value = mode;
  };

  const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'card' ? 'table' : 'card';
  };

  const isCardView = computed(() => viewMode.value === 'card');
  const isTableView = computed(() => viewMode.value === 'table');

  return {
    viewMode,
    setViewMode,
    toggleViewMode,
    isCardView,
    isTableView,
  };
}
