<script setup lang="ts">
import { ref, watch } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { healthApi } from '@/services/api';

// Track consecutive failures to avoid flapping
const failureCount = ref(0);
const isDisconnected = ref(false);

const { isError, isSuccess } = useQuery({
  queryKey: ['health'],
  queryFn: healthApi.check,
  refetchInterval: 15000, // Check every 15 seconds
  retry: 2, // Retry twice before reporting error
  retryDelay: 1000,
  staleTime: 10000,
});

// Only show disconnected after 2 consecutive failures
watch(isError, (error) => {
  if (error) {
    failureCount.value++;
    if (failureCount.value >= 2) {
      isDisconnected.value = true;
    }
  }
});

// Reset on success
watch(isSuccess, (success) => {
  if (success) {
    failureCount.value = 0;
    isDisconnected.value = false;
  }
});
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Status dot -->
    <div
      class="h-2 w-2 rounded-full"
      :class="isDisconnected ? 'bg-status-failed' : 'bg-accent-success animate-pulse'"
    />
    <!-- Status text -->
    <span class="text-sm font-medium text-text-muted">
      {{ isDisconnected ? 'Disconnected' : 'Live' }}
    </span>
  </div>
</template>
