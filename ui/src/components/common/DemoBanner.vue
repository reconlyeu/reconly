<script setup lang="ts">
/**
 * DemoBanner - Shows a dismissible banner when running in demo mode.
 *
 * Displays an amber/yellow notification banner at the top of the page
 * when the application is running with RECONLY_DEMO_MODE=true.
 * Users can dismiss the banner, and this preference is stored in sessionStorage.
 */
import { onMounted, ref } from 'vue';
import { X, Info } from 'lucide-vue-next';
import { useDemoStore } from '@/stores/demo';
import { strings } from '@/i18n/en';

const demoStore = useDemoStore();
const isAnimatingOut = ref(false);

onMounted(async () => {
  await demoStore.fetchDemoMode();
});

function handleDismiss() {
  // Start exit animation
  isAnimatingOut.value = true;
  // Wait for animation to complete before actually dismissing
  setTimeout(() => {
    demoStore.dismissBanner();
    isAnimatingOut.value = false;
  }, 200);
}
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 -translate-y-full"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 -translate-y-full"
  >
    <div
      v-if="demoStore.showBanner && !isAnimatingOut"
      class="relative z-50 bg-gradient-to-r from-amber-500/90 to-amber-600/90 text-amber-950"
      role="banner"
      aria-label="Demo mode notification"
    >
      <div class="mx-auto max-w-7xl px-4 py-2.5 sm:px-6 lg:px-8">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <!-- Content -->
          <div class="flex items-center gap-2 sm:gap-3">
            <Info :size="18" class="shrink-0" aria-hidden="true" />
            <p class="text-sm font-medium">
              <span class="hidden sm:inline">{{ strings.demo.bannerFull }}</span>
              <span class="sm:hidden">{{ strings.demo.bannerShort }}</span>
            </p>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-3">
            <a
              href="https://github.com/reconlyeu/reconly#quick-start"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm font-medium underline underline-offset-2 hover:no-underline transition-all"
            >
              {{ strings.demo.learnMore }}
              <span aria-hidden="true"> &rarr;</span>
            </a>

            <!-- Dismiss button -->
            <button
              type="button"
              @click="handleDismiss"
              class="rounded-md p-1 hover:bg-amber-700/20 focus:outline-none focus:ring-2 focus:ring-amber-800 focus:ring-offset-1 focus:ring-offset-amber-500 transition-colors"
              :aria-label="strings.demo.dismiss"
            >
              <X :size="18" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
