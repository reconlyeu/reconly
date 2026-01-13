/**
 * Authentication store for OSS password protection
 *
 * Manages authentication state for password-protected deployments.
 * Checks /api/auth/config on app load to determine if auth is required.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { authApi, type AuthConfig } from '@/services/api';

export const useAuthStore = defineStore('auth', () => {
  // State
  const authConfig = ref<AuthConfig | null>(null);
  const isLoading = ref(true);
  const isAuthenticated = ref(false);
  const error = ref<string | null>(null);

  // Getters
  const authRequired = computed(() => authConfig.value?.auth_required ?? false);
  const edition = computed(() => authConfig.value?.edition ?? 'oss');

  /**
   * Check authentication configuration from API.
   * Should be called on app initialization.
   */
  async function checkAuthConfig(): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      authConfig.value = await authApi.getConfig();

      // If auth is not required, we're automatically authenticated
      if (!authConfig.value.auth_required) {
        isAuthenticated.value = true;
      }
    } catch (err: any) {
      // If we get a 401, auth is required and we're not authenticated
      if (err.status_code === 401) {
        authConfig.value = { auth_required: true, edition: 'oss' };
        isAuthenticated.value = false;
      } else {
        error.value = err.detail || 'Failed to check authentication status';
        // Assume auth is not required on error (graceful degradation)
        isAuthenticated.value = true;
      }
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Login with password.
   */
  async function login(password: string): Promise<boolean> {
    try {
      const response = await authApi.login(password);
      if (response.success) {
        isAuthenticated.value = true;
        return true;
      }
      return false;
    } catch (err: any) {
      error.value = err.detail || 'Login failed';
      return false;
    }
  }

  /**
   * Logout and clear session.
   */
  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      isAuthenticated.value = false;
      // Redirect to login page
      window.location.href = '/login';
    }
  }

  /**
   * Check if the current user needs to authenticate.
   * Returns true if they should be redirected to login.
   */
  function requiresLogin(): boolean {
    return authRequired.value && !isAuthenticated.value;
  }

  return {
    // State
    authConfig,
    isLoading,
    isAuthenticated,
    error,

    // Getters
    authRequired,
    edition,

    // Actions
    checkAuthConfig,
    login,
    logout,
    requiresLogin,
  };
});
