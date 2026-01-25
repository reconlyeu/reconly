<script setup lang="ts">
import { ref, watch } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { settingsApi } from '@/services/api';
import SettingField from './SettingField.vue';
import { useToast } from '@/composables/useToast';
import { Loader2, Save, RotateCcw, Bot } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { SettingValue } from '@/types/entities';

interface AgentSettings {
  search_provider: string;
  searxng_url: string;
  tavily_api_key: string;
  max_search_results: number;
  default_max_iterations: number;
  gptr_report_format: string;
  gptr_max_subtopics: number;
}

// Default values for agent settings
const DEFAULTS: AgentSettings = {
  search_provider: 'duckduckgo',
  searxng_url: '',
  tavily_api_key: '',
  max_search_results: 10,
  default_max_iterations: 5,
  gptr_report_format: 'APA',
  gptr_max_subtopics: 3,
};

// Setting keys that can be reset (excludes env-only keys like tavily_api_key)
const RESETTABLE_KEYS = [
  'agent.search_provider',
  'agent.searxng_url',
  'agent.max_search_results',
  'agent.default_max_iterations',
  'agent.gptr_report_format',
  'agent.gptr_max_subtopics',
];

const queryClient = useQueryClient();
const toast = useToast();

const { data: settings, isLoading } = useQuery({
  queryKey: ['settings', 'agent'],
  queryFn: () => settingsApi.get('agent'),
  staleTime: 30000,
});

const localSettings = ref<AgentSettings>({ ...DEFAULTS });
const hasChanges = ref(false);

// Get agent setting with fallback
function getAgentSetting(key: keyof AgentSettings): SettingValue {
  const setting = settings.value?.categories?.agent?.[key];
  if (!setting) {
    return { value: null, source: 'default', editable: true };
  }
  return setting;
}

// Update local settings from fetched data
function updateLocalFromSettings(): void {
  const agent = settings.value?.categories?.agent;
  if (!agent) return;

  for (const key of Object.keys(DEFAULTS) as Array<keyof AgentSettings>) {
    const setting = agent[key];
    if (setting?.value === undefined) continue;

    const defaultValue = DEFAULTS[key];
    if (typeof defaultValue === 'number') {
      localSettings.value[key] = Number(setting.value) || defaultValue;
    } else {
      localSettings.value[key] = String(setting.value || defaultValue) as never;
    }
  }
  hasChanges.value = false;
}

watch(settings, updateLocalFromSettings, { immediate: true });

function handleUpdate<K extends keyof AgentSettings>(key: K, value: AgentSettings[K]): void {
  localSettings.value[key] = value;
  hasChanges.value = true;
}

// Select options
const searchProviderOptions = [
  { value: 'duckduckgo', label: 'DuckDuckGo' },
  { value: 'searxng', label: 'SearXNG' },
  { value: 'tavily', label: 'Tavily' },
];

const reportFormatOptions = [
  { value: 'APA', label: 'APA' },
  { value: 'MLA', label: 'MLA' },
  { value: 'CMS', label: 'Chicago (CMS)' },
  { value: 'Harvard', label: 'Harvard' },
  { value: 'IEEE', label: 'IEEE' },
];

const saveMutation = useMutation({
  mutationFn: async () => {
    const settingsToUpdate = RESETTABLE_KEYS.map((fullKey) => {
      const key = fullKey.replace('agent.', '') as keyof AgentSettings;
      return { key: fullKey, value: localSettings.value[key] };
    });

    // Include tavily_api_key only if editable
    if (getAgentSetting('tavily_api_key').editable) {
      settingsToUpdate.push({ key: 'agent.tavily_api_key', value: localSettings.value.tavily_api_key });
    }

    return settingsApi.update({ settings: settingsToUpdate });
  },
  onSuccess: () => {
    toast.success(strings.settings.agent.settingsSaved);
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: Error & { detail?: string }) => {
    toast.error(err.detail || strings.settings.failedToSave);
  },
});

const resetMutation = useMutation({
  mutationFn: () => settingsApi.reset({ keys: RESETTABLE_KEYS }),
  onSuccess: () => {
    toast.success(strings.settings.agent.settingsReset);
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: Error & { detail?: string }) => {
    toast.error(err.detail || strings.settings.failedToReset);
  },
});
</script>

<template>
  <div class="space-y-6">
    <!-- Agent Settings Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
      <div class="flex items-center gap-3 mb-6">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
          <Bot :size="20" class="text-accent-primary" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-text-primary">{{ strings.settings.agent.title }}</h2>
          <p class="text-sm text-text-muted">{{ strings.settings.agent.description }}</p>
        </div>
      </div>

      <div v-if="isLoading" class="flex items-center justify-center py-12">
        <Loader2 :size="32" class="animate-spin text-accent-primary" />
      </div>

      <div v-else class="space-y-6">
        <!-- Search Settings Section -->
        <div class="space-y-4">
          <h3 class="text-sm font-medium text-text-secondary uppercase tracking-wide">{{ strings.settings.agent.searchSettings }}</h3>
          <div class="grid gap-6 md:grid-cols-2">
            <!-- Search Provider -->
            <SettingField
              setting-key="search_provider"
              :setting="{ value: localSettings.search_provider, source: getAgentSetting('search_provider').source, editable: true }"
              :label="strings.settings.agent.fields.searchProvider"
              type="select"
              :options="searchProviderOptions"
              :description="strings.settings.agent.fields.searchProviderDescription"
              @update="handleUpdate('search_provider', $event)"
            />

            <!-- Max Search Results -->
            <SettingField
              setting-key="max_search_results"
              :setting="{ value: localSettings.max_search_results, source: getAgentSetting('max_search_results').source, editable: true }"
              :label="strings.settings.agent.fields.maxSearchResults"
              type="number"
              :description="strings.settings.agent.fields.maxSearchResultsDescription"
              @update="handleUpdate('max_search_results', $event)"
            />
          </div>

          <!-- SearXNG URL (shown when searxng provider selected) -->
          <SettingField
            v-if="localSettings.search_provider === 'searxng'"
            setting-key="searxng_url"
            :setting="{ value: localSettings.searxng_url, source: getAgentSetting('searxng_url').source, editable: getAgentSetting('searxng_url').editable }"
            :label="strings.settings.agent.fields.searxngUrl"
            type="text"
            :description="strings.settings.agent.fields.searxngUrlDescription"
            @update="handleUpdate('searxng_url', $event)"
          />

          <!-- Tavily API Key (shown when tavily provider selected) -->
          <SettingField
            v-if="localSettings.search_provider === 'tavily'"
            setting-key="tavily_api_key"
            :setting="{ value: localSettings.tavily_api_key, source: getAgentSetting('tavily_api_key').source, editable: getAgentSetting('tavily_api_key').editable }"
            :label="strings.settings.agent.fields.tavilyApiKey"
            type="password"
            :description="strings.settings.agent.fields.tavilyApiKeyDescription"
            @update="handleUpdate('tavily_api_key', $event)"
          />
        </div>

        <!-- Research Settings Section -->
        <div class="space-y-4 pt-4 border-t border-border-subtle">
          <h3 class="text-sm font-medium text-text-secondary uppercase tracking-wide">{{ strings.settings.agent.researchSettings }}</h3>
          <div class="grid gap-6 md:grid-cols-2">
            <!-- Default Max Iterations -->
            <SettingField
              setting-key="default_max_iterations"
              :setting="{ value: localSettings.default_max_iterations, source: getAgentSetting('default_max_iterations').source, editable: true }"
              :label="strings.settings.agent.fields.defaultMaxIterations"
              type="number"
              :description="strings.settings.agent.fields.defaultMaxIterationsDescription"
              @update="handleUpdate('default_max_iterations', $event)"
            />

            <!-- GPT Researcher Report Format -->
            <SettingField
              setting-key="gptr_report_format"
              :setting="{ value: localSettings.gptr_report_format, source: getAgentSetting('gptr_report_format').source, editable: true }"
              :label="strings.settings.agent.fields.gptrReportFormat"
              type="select"
              :options="reportFormatOptions"
              :description="strings.settings.agent.fields.gptrReportFormatDescription"
              @update="handleUpdate('gptr_report_format', $event)"
            />

            <!-- GPT Researcher Max Subtopics -->
            <SettingField
              setting-key="gptr_max_subtopics"
              :setting="{ value: localSettings.gptr_max_subtopics, source: getAgentSetting('gptr_max_subtopics').source, editable: true }"
              :label="strings.settings.agent.fields.gptrMaxSubtopics"
              type="number"
              :description="strings.settings.agent.fields.gptrMaxSubtopicsDescription"
              @update="handleUpdate('gptr_max_subtopics', $event)"
            />
          </div>
        </div>

        <!-- Save/Reset Buttons -->
        <div class="flex justify-end gap-3 pt-4 border-t border-border-subtle">
          <button
            type="button"
            :disabled="resetMutation.isPending.value"
            @click="resetMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-secondary hover:bg-bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw :size="16" />
            {{ strings.settings.resetToDefaults }}
          </button>
          <button
            type="button"
            :disabled="!hasChanges || saveMutation.isPending.value"
            @click="saveMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="saveMutation.isPending.value" :size="16" class="animate-spin" />
            <Save v-else :size="16" />
            {{ strings.settings.saveChanges }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
