<script setup lang="ts">
import { ref, computed } from 'vue';
import { useMutation } from '@tanstack/vue-query';
import { authApi } from '@/services/api';
import { Loader2, AlertCircle } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

const password = ref('');
const errorMessage = ref('');

const loginMutation = useMutation({
  mutationFn: (password: string) => authApi.login(password),
  onSuccess: () => {
    // Redirect to dashboard on successful login
    window.location.href = '/';
  },
  onError: (error: any) => {
    errorMessage.value = error.detail || strings.auth.login.failed;
  },
});

const handleSubmit = (e: Event) => {
  e.preventDefault();
  errorMessage.value = '';

  if (!password.value) {
    errorMessage.value = strings.auth.login.passwordRequired;
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
        <img src="/reconly-logo.png" :alt="strings.app.name" class="w-16 h-16 mx-auto mb-4" />
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.app.name }}</h1>
        <p class="text-text-secondary mt-2">{{ strings.auth.login.subtitle }}</p>
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
          <label for="password" class="sr-only">{{ strings.auth.login.password }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            :placeholder="strings.auth.login.password"
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
          <span>{{ isSubmitting ? strings.auth.login.submitting : strings.auth.login.submit }}</span>
        </button>
      </form>

      <!-- Footer -->
      <p class="text-center text-text-muted text-sm mt-8">
        {{ strings.auth.login.protected }}
      </p>
    </div>
  </div>
</template>
