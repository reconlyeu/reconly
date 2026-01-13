<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Sun, Moon } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

const isDark = ref(true);

onMounted(() => {
  // Check current theme
  isDark.value = document.documentElement.classList.contains('dark');
});

const toggleTheme = () => {
  isDark.value = !isDark.value;
  const theme = isDark.value ? 'dark' : 'light';

  // Update DOM
  document.documentElement.classList.remove('light', 'dark');
  document.documentElement.classList.add(theme);

  // Persist preference
  localStorage.setItem('theme', theme);
};
</script>

<template>
  <button
    @click="toggleTheme"
    class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
    :title="isDark ? strings.common.lightMode : strings.common.darkMode"
    :aria-label="isDark ? strings.common.lightMode : strings.common.darkMode"
  >
    <Moon v-if="isDark" class="w-5 h-5" />
    <Sun v-else class="w-5 h-5" />
  </button>
</template>
