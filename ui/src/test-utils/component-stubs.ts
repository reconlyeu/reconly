/**
 * Shared component stubs for Vue Test Utils.
 * Use these stubs to mock child components in tests.
 */

/**
 * Common stubs for list-based components (BaseList, BaseTable).
 */
export const listComponentStubs = {
  LoadingSkeleton: {
    template: '<div data-testid="loading-skeleton" />',
  },
  ErrorState: {
    template: '<div data-testid="error-state"><slot name="action" /></div>',
    props: ['entityName', 'error', 'showRetry'],
  },
  EmptyState: {
    template: '<div data-testid="empty-state"><slot name="action" /></div>',
    props: ['title', 'message', 'icon'],
  },
  Pagination: {
    template: '<div data-testid="pagination" />',
    props: ['page', 'totalPages', 'hasNext', 'hasPrev'],
  },
};

/**
 * Stub for ErrorState that emits retry event.
 */
export const errorStateWithRetry = {
  template: '<div data-testid="error-state"><button @click="$emit(\'retry\')">Retry</button></div>',
  emits: ['retry'],
};

/**
 * Stub for Pagination that emits prev/next events.
 */
export const paginationWithEvents = {
  template: '<div><button @click="$emit(\'prev\')">Prev</button><button @click="$emit(\'next\')">Next</button></div>',
  emits: ['prev', 'next'],
};

/**
 * Lucide icon stubs for components using icons.
 */
export const iconStubs = {
  ChevronLeft: true,
  ChevronRight: true,
};
