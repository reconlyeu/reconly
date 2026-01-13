/**
 * Composable for managing pagination state.
 * Encapsulates page, offset calculation, and navigation helpers.
 */
import { ref, computed, type Ref } from 'vue';

export interface UsePaginationOptions {
  /** Items per page */
  pageSize?: number;
  /** Initial page number (1-based) */
  initialPage?: number;
  /** Total items count (reactive ref) */
  total?: Ref<number>;
}

export function usePagination(options: UsePaginationOptions = {}) {
  const { pageSize = 10, initialPage = 1, total } = options;

  const page = ref(initialPage);
  const perPage = ref(pageSize);

  const offset = computed(() => (page.value - 1) * perPage.value);

  const totalPages = computed(() => {
    if (!total?.value) return 1;
    return Math.ceil(total.value / perPage.value);
  });

  const hasNext = computed(() => page.value < totalPages.value);
  const hasPrev = computed(() => page.value > 1);

  const isFirstPage = computed(() => page.value === 1);
  const isLastPage = computed(() => page.value >= totalPages.value);

  const nextPage = () => {
    if (hasNext.value) {
      page.value++;
    }
  };

  const prevPage = () => {
    if (hasPrev.value) {
      page.value--;
    }
  };

  const goToPage = (pageNum: number) => {
    if (pageNum >= 1 && pageNum <= totalPages.value) {
      page.value = pageNum;
    }
  };

  const reset = () => {
    page.value = 1;
  };

  const setPageSize = (newSize: number) => {
    perPage.value = newSize;
    // Reset to first page when page size changes
    page.value = 1;
  };

  return {
    // State
    page,
    perPage,
    offset,
    totalPages,
    // Computed flags
    hasNext,
    hasPrev,
    isFirstPage,
    isLastPage,
    // Methods
    nextPage,
    prevPage,
    goToPage,
    reset,
    setPageSize,
  };
}
