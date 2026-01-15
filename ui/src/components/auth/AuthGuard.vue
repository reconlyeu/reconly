<script setup lang="ts">
/**
 * AuthGuard component - checks authentication status on mount.
 *
 * If auth is required and user is not authenticated, redirects to /login.
 * Use in BaseLayout to protect all pages.
 */
import { onMounted, ref } from 'vue';
import { Loader2 } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth';

const isChecking = ref(true);

onMounted(async () => {
  // Access store inside onMounted to ensure Pinia is initialized
  const authStore = useAuthStore();
  await authStore.checkAuthConfig();

  // If auth is required and not authenticated, redirect to login
  if (authStore.requiresLogin()) {
    window.location.href = '/login';
    return;
  }

  isChecking.value = false;
});
</script>

<template>
  <!-- Loading state while checking auth -->
  <div v-if="isChecking" class="fixed inset-0 flex items-center justify-center bg-bg-base">
    <Loader2 :size="32" class="animate-spin text-accent-primary" />
  </div>

  <!-- Content shown when authenticated -->
  <slot v-else />
</template>
