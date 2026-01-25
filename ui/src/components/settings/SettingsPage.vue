<script setup lang="ts">
import { ref, watch } from 'vue';
import { strings } from '@/i18n/en';
import ProviderChain from './ProviderChain.vue';
import EmailSettings from './EmailSettings.vue';
import ExportSettings from './ExportSettings.vue';
import FetcherSettings from './FetcherSettings.vue';
import ExtensionsSection from './ExtensionsSection.vue';
import AgentSettings from './AgentSettings.vue';
import { useSettingsNavigation, type SettingsTab } from '@/composables/useSettingsNavigation';

const activeTab = ref<SettingsTab>('providers');
const { pendingNavigation, consumeNavigation } = useSettingsNavigation();

// Switch tab (simple, no URL manipulation)
const switchTab = (tab: SettingsTab) => {
  activeTab.value = tab;
};

// Watch for navigation requests from other components (e.g., ExtensionCard)
watch(pendingNavigation, (target) => {
  if (target) {
    activeTab.value = target.tab;
    consumeNavigation();
  }
}, { immediate: true });

const tabs = [
  { key: 'providers' as const, label: strings.settings.tabs.providers },
  { key: 'fetchers' as const, label: strings.settings.tabs.fetchers },
  { key: 'exports' as const, label: strings.settings.tabs.exports },
  { key: 'agent' as const, label: strings.settings.tabs.agent },
  { key: 'extensions' as const, label: strings.settings.tabs.extensions },
  { key: 'email' as const, label: strings.settings.tabs.email },
];
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text-primary">{{ strings.settings.title }}</h1>
      <p class="mt-1 text-sm text-text-secondary">
        Configure providers, email delivery, and export options
      </p>
    </div>

    <!-- Tabs -->
    <div class="mb-6 flex gap-4 border-b border-border-subtle">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="switchTab(tab.key)"
        class="border-b-2 px-4 py-3 font-medium transition-all"
        :class="
          activeTab === tab.key
            ? 'border-accent-primary text-accent-primary'
            : 'border-transparent text-text-muted hover:text-text-primary'
        "
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab Content -->
    <div>
      <!-- Fetchers Tab -->
      <div v-if="activeTab === 'fetchers'">
        <FetcherSettings />
      </div>

      <!-- Providers Tab -->
      <div v-if="activeTab === 'providers'">
        <ProviderChain />
      </div>

      <!-- Exports Tab -->
      <div v-if="activeTab === 'exports'">
        <ExportSettings />
      </div>

      <!-- Agent Tab -->
      <div v-if="activeTab === 'agent'">
        <AgentSettings />
      </div>

      <!-- Extensions Tab -->
      <div v-if="activeTab === 'extensions'">
        <ExtensionsSection />
      </div>

      <!-- Email Tab -->
      <div v-if="activeTab === 'email'">
        <EmailSettings />
      </div>
    </div>
  </div>
</template>

