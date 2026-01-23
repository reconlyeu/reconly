/**
 * Composable for managing onboarding wizard state
 *
 * Tracks whether the user has completed onboarding via localStorage.
 * Shows the wizard only once on first startup.
 */

import { ref, onMounted, computed } from 'vue';

const ONBOARDING_KEY = 'reconly_onboarding_complete';

// Shared state across components
const isOnboardingComplete = ref<boolean | null>(null);
const showWizard = ref(false);

/**
 * Check if onboarding has been completed
 */
function checkOnboardingStatus(): boolean {
  if (typeof window === 'undefined') return true;
  const value = localStorage.getItem(ONBOARDING_KEY);
  return value === 'true';
}

/**
 * Mark onboarding as complete
 */
function completeOnboarding(): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ONBOARDING_KEY, 'true');
  isOnboardingComplete.value = true;
  showWizard.value = false;
}

/**
 * Reset onboarding status (for testing)
 */
function resetOnboarding(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ONBOARDING_KEY);
  isOnboardingComplete.value = false;
}

export function useOnboarding() {
  // Initialize state on mount
  onMounted(() => {
    if (isOnboardingComplete.value === null) {
      isOnboardingComplete.value = checkOnboardingStatus();
      // Show wizard if onboarding is not complete
      if (!isOnboardingComplete.value) {
        showWizard.value = true;
      }
    }
  });

  const shouldShowWizard = computed(() => {
    // Return false during SSR or if already completed
    if (isOnboardingComplete.value === null) return false;
    return showWizard.value && !isOnboardingComplete.value;
  });

  const openWizard = () => {
    showWizard.value = true;
  };

  const closeWizard = () => {
    showWizard.value = false;
  };

  const skipOnboarding = () => {
    completeOnboarding();
  };

  const finishOnboarding = () => {
    completeOnboarding();
  };

  return {
    isOnboardingComplete: computed(() => isOnboardingComplete.value === true),
    shouldShowWizard,
    openWizard,
    closeWizard,
    skipOnboarding,
    finishOnboarding,
    resetOnboarding,
  };
}
