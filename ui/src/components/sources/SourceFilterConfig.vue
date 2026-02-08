<script setup lang="ts">
import { ref, computed } from 'vue';
import type { FilterMode } from '@/types/entities';
import { Filter, Plus, X, AlertCircle } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

const maxItems = defineModel<number | null>('maxItems', { default: null });
const includeKeywords = defineModel<string[]>('includeKeywords', { default: () => [] });
const excludeKeywords = defineModel<string[]>('excludeKeywords', { default: () => [] });
const filterMode = defineModel<FilterMode>('filterMode', { default: 'both' });
const useRegex = defineModel<boolean>('useRegex', { default: false });

const showFilters = ref(false);
const includeInput = ref('');
const excludeInput = ref('');
const regexError = ref<string | null>(null);

const validateRegex = (pattern: string): boolean => {
  if (!useRegex.value) return true;
  try {
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
};

const addIncludeKeyword = () => {
  const keyword = includeInput.value.trim();
  if (keyword && !includeKeywords.value.includes(keyword)) {
    if (useRegex.value && !validateRegex(keyword)) {
      regexError.value = `Invalid regex: ${keyword}`;
      return;
    }
    includeKeywords.value.push(keyword);
    regexError.value = null;
  }
  includeInput.value = '';
};

const addExcludeKeyword = () => {
  const keyword = excludeInput.value.trim();
  if (keyword && !excludeKeywords.value.includes(keyword)) {
    if (useRegex.value && !validateRegex(keyword)) {
      regexError.value = `Invalid regex: ${keyword}`;
      return;
    }
    excludeKeywords.value.push(keyword);
    regexError.value = null;
  }
  excludeInput.value = '';
};

const removeIncludeKeyword = (index: number) => {
  includeKeywords.value.splice(index, 1);
};

const removeExcludeKeyword = (index: number) => {
  excludeKeywords.value.splice(index, 1);
};

const hasFilters = computed(() => {
  return maxItems.value !== null || includeKeywords.value.length > 0 || excludeKeywords.value.length > 0;
});

const activeFilterCount = computed(() => {
  let count = includeKeywords.value.length + excludeKeywords.value.length;
  if (maxItems.value !== null) count++;
  return count;
});

const reset = () => {
  showFilters.value = false;
  includeInput.value = '';
  excludeInput.value = '';
  regexError.value = null;
};

const initFilters = (hasExisting: boolean) => {
  showFilters.value = hasExisting;
};

defineExpose({ reset, initFilters });
</script>

<template>
  <div class="rounded-lg border border-border-subtle bg-bg-surface">
    <!-- Toggle Header -->
    <button
      type="button"
      @click="showFilters = !showFilters"
      class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-bg-hover"
    >
      <div class="flex items-center gap-2">
        <Filter :size="18" class="text-text-muted" />
        <span class="text-sm font-medium text-text-primary">{{ strings.sources.form.filters }}</span>
        <span v-if="hasFilters" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
          {{ activeFilterCount }} {{ strings.sources.form.active }}
        </span>
      </div>
      <span class="text-xs text-text-muted">{{ showFilters ? strings.sources.form.hide : strings.sources.form.show }}</span>
    </button>

    <!-- Filter Content -->
    <Transition name="slide">
      <div v-if="showFilters" class="border-t border-border-subtle p-4 space-y-4">
        <!-- Max Items -->
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            {{ strings.sources.fields.maxItemsPerRun }}
          </label>
          <p class="mb-2 text-xs text-text-muted">
            {{ strings.sources.filterHints.maxItems }}
          </p>
          <input
            v-model.number="maxItems"
            type="number"
            min="1"
            max="100"
            :placeholder="strings.sources.placeholders.noLimit"
            class="w-32 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
          />
        </div>

        <!-- Regex Error -->
        <div v-if="regexError" class="flex items-center gap-2 rounded-lg bg-status-failed/10 p-3 text-sm text-status-failed">
          <AlertCircle :size="16" />
          {{ regexError }}
        </div>

        <!-- Include Keywords -->
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            {{ strings.sources.fields.includeKeywords }}
          </label>
          <p class="mb-2 text-xs text-text-muted">
            {{ strings.sources.filterHints.includeKeywords }}
          </p>
          <div class="flex gap-2">
            <input
              v-model="includeInput"
              type="text"
              :placeholder="strings.sources.placeholders.addKeyword"
              @keydown.enter.prevent="addIncludeKeyword"
              class="flex-1 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
            <button
              type="button"
              @click="addIncludeKeyword"
              class="rounded-lg border border-border-subtle bg-bg-base p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              <Plus :size="18" />
            </button>
          </div>
          <div v-if="includeKeywords.length" class="mt-2 flex flex-wrap gap-2">
            <span
              v-for="(keyword, index) in includeKeywords"
              :key="index"
              class="flex items-center gap-1 rounded-full bg-status-success/20 px-2.5 py-1 text-xs text-status-success"
            >
              {{ keyword }}
              <button
                type="button"
                @click="removeIncludeKeyword(index)"
                class="ml-1 rounded-full p-0.5 transition-colors hover:bg-status-success/30"
              >
                <X :size="12" />
              </button>
            </span>
          </div>
        </div>

        <!-- Exclude Keywords -->
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            {{ strings.sources.fields.excludeKeywords }}
          </label>
          <p class="mb-2 text-xs text-text-muted">
            {{ strings.sources.filterHints.excludeKeywords }}
          </p>
          <div class="flex gap-2">
            <input
              v-model="excludeInput"
              type="text"
              :placeholder="strings.sources.placeholders.addKeyword"
              @keydown.enter.prevent="addExcludeKeyword"
              class="flex-1 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
            <button
              type="button"
              @click="addExcludeKeyword"
              class="rounded-lg border border-border-subtle bg-bg-base p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              <Plus :size="18" />
            </button>
          </div>
          <div v-if="excludeKeywords.length" class="mt-2 flex flex-wrap gap-2">
            <span
              v-for="(keyword, index) in excludeKeywords"
              :key="index"
              class="flex items-center gap-1 rounded-full bg-status-failed/20 px-2.5 py-1 text-xs text-status-failed"
            >
              {{ keyword }}
              <button
                type="button"
                @click="removeExcludeKeyword(index)"
                class="ml-1 rounded-full p-0.5 transition-colors hover:bg-status-failed/30"
              >
                <X :size="12" />
              </button>
            </span>
          </div>
        </div>

        <!-- Filter Mode & Regex Toggle -->
        <div class="flex gap-4">
          <!-- Filter Mode -->
          <div class="flex-1">
            <label class="mb-2 block text-sm font-medium text-text-primary">
              {{ strings.sources.fields.searchIn }}
            </label>
            <select
              v-model="filterMode"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            >
              <option value="both">{{ strings.sources.filterModes.both }}</option>
              <option value="title_only">{{ strings.sources.filterModes.titleOnly }}</option>
              <option value="content">{{ strings.sources.filterModes.content }}</option>
            </select>
          </div>

          <!-- Use Regex Toggle -->
          <div class="flex items-end">
            <button
              type="button"
              @click="useRegex = !useRegex"
              class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors"
              :class="useRegex
                ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                : 'border-border-subtle bg-bg-base text-text-muted hover:bg-bg-hover hover:text-text-primary'"
            >
              <span class="font-mono text-xs">.*</span>
              {{ strings.sources.form.regex }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Slide transitions for filter section */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
