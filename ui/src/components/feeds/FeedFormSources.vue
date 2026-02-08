<script setup lang="ts">
import { ref, computed } from 'vue';
import type { Source } from '@/types/entities';
import { Search, AlertTriangle } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  sources: Source[];
  errors?: Record<string, string | undefined>;
}

const props = defineProps<Props>();
const sourceIds = defineModel<number[]>('sourceIds', { required: true });

const sourceSearch = ref('');

// Capture initial selection when component mounts (for stable sorting during editing)
const initialSelectedIds = computed(() => new Set(sourceIds.value));

const filteredSources = computed(() => {
  if (!props.sources) return [];

  let result = [...props.sources];

  // Filter by search term if provided
  if (sourceSearch.value) {
    const search = sourceSearch.value.toLowerCase();
    result = result.filter(s =>
      s.name.toLowerCase().includes(search) ||
      s.url.toLowerCase().includes(search)
    );
  }

  // Sort: selected sources first (alphabetical), then unselected (alphabetical)
  result.sort((a, b) => {
    const aSelected = sourceIds.value.includes(a.id);
    const bSelected = sourceIds.value.includes(b.id);

    // Selected sources come first
    if (aSelected && !bSelected) return -1;
    if (!aSelected && bSelected) return 1;

    // Within same group, sort alphabetically by name
    return a.name.localeCompare(b.name);
  });

  return result;
});

// Track selected disabled sources to show warning
const selectedDisabledSources = computed(() => {
  if (!props.sources) return [];
  return props.sources.filter(s =>
    sourceIds.value.includes(s.id) && s.enabled === false
  );
});

const toggleSource = (sourceId: number) => {
  const index = sourceIds.value.indexOf(sourceId);
  if (index === -1) {
    sourceIds.value.push(sourceId);
  } else {
    sourceIds.value.splice(index, 1);
  }
};

const isSourceSelected = (sourceId: number) => {
  return sourceIds.value.includes(sourceId);
};

const resetSearch = () => {
  sourceSearch.value = '';
};

defineExpose({ resetSearch });
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.selectSources }}</h3>
      <span class="text-sm text-text-secondary">
        {{ sourceIds.length }} {{ strings.feeds.sourceSelection.selected.replace('{count}', '') }}
      </span>
    </div>

    <!-- Search -->
    <div class="relative">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
      <input
        v-model="sourceSearch"
        type="search"
        :placeholder="strings.feeds.placeholders.searchSources"
        class="w-full rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
      />
    </div>

    <!-- Source Checkboxes -->
    <div class="max-h-60 overflow-y-auto space-y-2 rounded-lg border border-border-subtle bg-bg-surface p-4">
      <label
        v-for="source in filteredSources"
        :key="source.id"
        class="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-bg-hover cursor-pointer"
        :class="{ 'opacity-60': source.enabled === false }"
      >
        <input
          type="checkbox"
          :checked="isSourceSelected(source.id)"
          @change="toggleSource(source.id)"
          class="h-4 w-4 rounded border-border-default bg-bg-elevated text-accent-primary focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-text-primary">{{ source.name }}</span>
            <span
              v-if="source.enabled === false"
              class="text-xs font-medium px-1.5 py-0.5 rounded bg-text-muted/20 text-text-muted"
            >
              {{ strings.feeds.sourceSelection.disabled }}
            </span>
          </div>
          <div class="text-xs text-text-muted truncate">{{ source.url }}</div>
        </div>
        <span
          class="text-xs font-medium px-2 py-1 rounded-full"
          :class="{
            'bg-orange-400/10 text-orange-400': source.type === 'rss',
            'bg-red-500/10 text-red-500': source.type === 'youtube',
            'bg-blue-400/10 text-blue-400': source.type === 'website',
            'bg-green-400/10 text-green-400': source.type === 'blog',
          }"
        >
          {{ source.type }}
        </span>
      </label>

      <div v-if="filteredSources?.length === 0" class="py-8 text-center text-sm text-text-muted">
        {{ strings.feeds.sourceSelection.noSourcesFound }}
      </div>
    </div>

    <!-- Warning for disabled sources selected -->
    <Transition name="error">
      <div
        v-if="selectedDisabledSources.length > 0"
        class="mt-2 flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3"
      >
        <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
        <p class="text-xs text-amber-200">
          {{ strings.feeds.sourceSelection.disabledSourcesWarning.replace('{count}', String(selectedDisabledSources.length)) }}
        </p>
      </div>
    </Transition>

    <Transition name="error">
      <p v-if="errors?.source_ids" class="mt-2 text-sm text-status-failed">{{ errors.source_ids }}</p>
    </Transition>
  </div>
</template>
