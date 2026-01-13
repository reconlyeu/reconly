/**
 * Vue app entry point for Astro integration
 *
 * This file configures Vue plugins that are shared across all Vue islands:
 * - Pinia for state management
 * - TanStack Vue Query for data fetching
 * - Vue Toastification for toast notifications
 */

import type { App } from 'vue';
import { createPinia } from 'pinia';
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query';
import ToastPlugin from 'vue-toastification';
import 'vue-toastification/dist/index.css';
import { toastOptions } from './plugins/toast';

// Handle ESM interop - the plugin might be at .default
const Toast = (ToastPlugin as any).default || ToastPlugin;

// Create a single Pinia instance for all Vue islands
const pinia = createPinia();

// Configure Vue Query client with sensible defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: 30 seconds before refetching
      staleTime: 30 * 1000,
      // Cache time: 5 minutes
      gcTime: 5 * 60 * 1000,
      // Retry failed requests up to 3 times
      retry: 3,
      // Refetch on window focus
      refetchOnWindowFocus: true,
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
    },
  },
});

/**
 * Astro Vue integration entry point
 * Called for each Vue island when it mounts
 */
export default (app: App) => {
  // Install Pinia
  app.use(pinia);

  // Install Vue Query
  app.use(VueQueryPlugin, { queryClient });

  // Install Toast notifications
  app.use(Toast, toastOptions);
};

// Export for use in stores
export { pinia, queryClient };
