/**
 * Pinia stores index
 *
 * Re-exports all stores for convenient imports:
 * import { useSourcesStore, useFeedsStore } from '@stores';
 */

export { useAuthStore } from './auth';
export { useSourcesStore } from './sources';
export { useFeedsStore } from './feeds';
export { useTemplatesStore } from './templates';
export { useDigestsStore } from './digests';
export { useAnalyticsStore } from './analytics';
