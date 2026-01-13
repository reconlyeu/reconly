/**
 * Composable for using toast notifications
 * Provides a simple interface to show success, error, warning, and info toasts
 *
 * Uses dynamic import to avoid SSR issues with vue-toastification.
 */

// Fallback console logger for SSR
const consoleFallback = {
  success: (message: string) => console.log('[Toast Success]', message),
  error: (message: string) => console.error('[Toast Error]', message),
  warning: (message: string) => console.warn('[Toast Warning]', message),
  info: (message: string) => console.info('[Toast Info]', message),
};

// Cached toast interface (loaded dynamically on first use)
let toastInterface: any = null;
let loadingPromise: Promise<any> | null = null;

async function loadToast() {
  if (toastInterface) return toastInterface;
  if (loadingPromise) return loadingPromise;

  loadingPromise = import('vue-toastification').then((module) => {
    const { globalEventBus, createToastInterface } = module;
    toastInterface = createToastInterface(globalEventBus);
    return toastInterface;
  });

  return loadingPromise;
}

export function useToast() {
  // Check if we're in a browser environment
  if (typeof window === 'undefined') {
    return consoleFallback;
  }

  // Eagerly load the toast module
  loadToast();

  return {
    success: (message: string) => {
      loadToast().then((toast) => toast.success(message));
    },
    error: (message: string) => {
      loadToast().then((toast) => toast.error(message));
    },
    warning: (message: string) => {
      loadToast().then((toast) => toast.warning(message));
    },
    info: (message: string) => {
      loadToast().then((toast) => toast.info(message));
    },
  };
}
