<script setup lang="ts">
import { ref, computed } from 'vue';
import { useMutation } from '@tanstack/vue-query';
import { authApi } from '@/services/api';
import { Lock, Loader2, AlertCircle } from 'lucide-vue-next';

const password = ref('');
const errorMessage = ref('');

const loginMutation = useMutation({
  mutationFn: (password: string) => authApi.login(password),
  onSuccess: () => {
    // Redirect to dashboard on successful login
    window.location.href = '/';
  },
  onError: (error: any) => {
    errorMessage.value = error.detail || 'Login failed. Please try again.';
  },
});

const handleSubmit = (e: Event) => {
  e.preventDefault();
  errorMessage.value = '';

  if (!password.value) {
    errorMessage.value = 'Please enter a password';
    return;
  }

  loginMutation.mutate(password.value);
};

const isSubmitting = computed(() => loginMutation.isPending.value);
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-bg-base p-4">
    <div class="w-full max-w-md">
      <!-- Logo/Brand -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-primary to-accent-primary/70 mb-4">
          <Lock :size="32" class="text-white" />
        </div>
        <h1 class="text-2xl font-bold text-text-primary">Reconly</h1>
        <p class="text-text-secondary mt-2">Enter your password to continue</p>
      </div>

      <!-- Login Form -->
      <form @submit="handleSubmit" class="space-y-6">
        <!-- Error Message -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-2 p-4 rounded-lg bg-status-failed/10 border border-status-failed/20 text-status-failed"
        >
          <AlertCircle :size="20" />
          <span class="text-sm">{{ errorMessage }}</span>
        </div>

        <!-- Password Input -->
        <div>
          <label for="password" class="sr-only">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="Password"
            autocomplete="current-password"
            :disabled="isSubmitting"
            class="w-full px-4 py-3 rounded-lg border border-border-subtle bg-bg-surface text-text-primary placeholder-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base disabled:opacity-50"
          />
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="isSubmitting"
          class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-accent-primary text-white font-medium hover:bg-accent-primary-hover focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Loader2 v-if="isSubmitting" :size="20" class="animate-spin" />
          <span>{{ isSubmitting ? 'Signing in...' : 'Sign In' }}</span>
        </button>
      </form>

      <!-- Footer -->
      <p class="text-center text-text-muted text-sm mt-8">
        This instance is password protected.
      </p>
    </div>
  </div>
</template>
