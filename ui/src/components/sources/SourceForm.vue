<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import * as z from 'zod';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { sourcesApi } from '@/services/api';
import type { Source, FilterMode } from '@/types/entities';
import { X, Loader2, Filter, Plus, AlertCircle } from 'lucide-vue-next';

interface Props {
  isOpen: boolean;
  source?: Source | null;
}

interface Emits {
  (e: 'close'): void;
  (e: 'success'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const queryClient = useQueryClient();

// Validation schema
const formSchema = toTypedSchema(
  z.object({
    name: z.string().min(1, 'Name is required').max(200, 'Name is too long'),
    type: z.enum(['rss', 'youtube', 'website', 'blog'], {
      errorMap: () => ({ message: 'Please select a source type' }),
    }),
    url: z.string().url('Must be a valid URL'),
    enabled: z.boolean(),
  })
);

// Form setup
const { defineField, handleSubmit, resetForm, errors } = useForm({
  validationSchema: formSchema,
  initialValues: {
    name: '',
    type: 'rss' as const,
    url: '',
    enabled: true,
  },
});

const [name, nameAttrs] = defineField('name');
const [type, typeAttrs] = defineField('type');
const [url, urlAttrs] = defineField('url');
const [enabled, enabledAttrs] = defineField('enabled');

// Filter fields (outside vee-validate for simplicity)
const showFilters = ref(false);
const maxItems = ref<number | null>(null);
const includeKeywords = ref<string[]>([]);
const excludeKeywords = ref<string[]>([]);
const filterMode = ref<FilterMode>('both');
const useRegex = ref(false);
const includeInput = ref('');
const excludeInput = ref('');
const regexError = ref<string | null>(null);

// Validate regex pattern
const validateRegex = (pattern: string): boolean => {
  if (!useRegex.value) return true;
  try {
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
};

// Add keyword chip
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

// Remove keyword chip
const removeIncludeKeyword = (index: number) => {
  includeKeywords.value.splice(index, 1);
};

const removeExcludeKeyword = (index: number) => {
  excludeKeywords.value.splice(index, 1);
};

// Reset filter fields
const resetFilterFields = () => {
  maxItems.value = null;
  includeKeywords.value = [];
  excludeKeywords.value = [];
  filterMode.value = 'both';
  useRegex.value = false;
  includeInput.value = '';
  excludeInput.value = '';
  regexError.value = null;
  showFilters.value = false;
};

// Watch for source prop changes (edit mode)
watch(
  () => props.source,
  (newSource) => {
    if (newSource) {
      resetForm({
        values: {
          name: newSource.name,
          type: newSource.type as 'rss' | 'youtube' | 'website' | 'blog',
          url: newSource.url,
          enabled: newSource.enabled,
        },
      });
      // Restore filter fields
      maxItems.value = newSource.config?.max_items ?? null;
      includeKeywords.value = newSource.include_keywords || [];
      excludeKeywords.value = newSource.exclude_keywords || [];
      filterMode.value = newSource.filter_mode || 'both';
      useRegex.value = newSource.use_regex || false;
      // Show filters section if any filters are configured
      showFilters.value = !!(maxItems.value || newSource.include_keywords?.length || newSource.exclude_keywords?.length);
    } else {
      resetForm();
      resetFilterFields();
    }
  },
  { immediate: true }
);

const isEditMode = computed(() => !!props.source);

// Create/Update mutation
const saveMutation = useMutation({
  mutationFn: async (data: any) => {
    // Build config object with max_items
    const config = maxItems.value ? { max_items: maxItems.value } : null;

    // Add filter fields to data
    const payload = {
      ...data,
      config,
      include_keywords: includeKeywords.value.length > 0 ? includeKeywords.value : null,
      exclude_keywords: excludeKeywords.value.length > 0 ? excludeKeywords.value : null,
      filter_mode: filterMode.value,
      use_regex: useRegex.value,
    };
    if (isEditMode.value && props.source) {
      return await sourcesApi.update(props.source.id, payload);
    } else {
      return await sourcesApi.create(payload);
    }
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
    emit('success');
    emit('close');
    resetForm();
    resetFilterFields();
  },
  onError: (error: any) => {
    console.error('Failed to save source:', error);
    // Mutation state will automatically reset to idle
  },
});

// Watch for modal open to reset mutation state
watch(
  () => props.isOpen,
  (isOpen) => {
    if (isOpen) {
      saveMutation.reset();
    }
  }
);

// Computed for reactive pending state
const isSaving = computed(() => saveMutation.isPending.value);

const onSubmit = handleSubmit((values) => {
  saveMutation.mutate(values);
});

const handleClose = () => {
  if (!isSaving.value) {
    emit('close');
    resetForm();
    resetFilterFields();
  }
};

// Computed to check if filters are configured
const hasFilters = computed(() => {
  return maxItems.value !== null || includeKeywords.value.length > 0 || excludeKeywords.value.length > 0;
});

// Count active filters for badge
const activeFilterCount = computed(() => {
  let count = includeKeywords.value.length + excludeKeywords.value.length;
  if (maxItems.value !== null) count++;
  return count;
});

// Dynamic URL placeholder based on type
const urlPlaceholder = computed(() => {
  const placeholders: Record<string, string> = {
    rss: 'https://example.com/feed.xml',
    youtube: 'https://youtube.com/@channel or /watch?v=...',
    website: 'https://example.com/article',
    blog: 'https://blog.example.com',
  };
  return placeholders[type.value] || 'https://example.com';
});
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="handleClose"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" />

        <!-- Modal -->
        <div
          class="relative w-full max-w-lg rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface p-8 shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orb -->
          <div class="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-accent-primary/20 blur-3xl" />

          <!-- Header -->
          <div class="relative mb-6 flex items-center justify-between">
            <h2 class="text-2xl font-bold text-text-primary">
              {{ isEditMode ? 'Edit Source' : 'Add New Source' }}
            </h2>
            <button
              @click="handleClose"
              :disabled="isSaving"
              class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
            >
              <X :size="20" />
            </button>
          </div>

          <!-- Form -->
          <form @submit.prevent="onSubmit" class="relative space-y-6">
            <!-- Name Field -->
            <div>
              <label for="name" class="mb-2 block text-sm font-medium text-text-primary">
                Name
              </label>
              <input
                id="name"
                v-model="name"
                v-bind="nameAttrs"
                type="text"
                placeholder="My RSS Feed"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.name
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.name" class="mt-2 text-sm text-status-failed">
                  {{ errors.name }}
                </p>
              </Transition>
            </div>

            <!-- Type Field -->
            <div>
              <label for="type" class="mb-2 block text-sm font-medium text-text-primary">
                Type
              </label>
              <select
                id="type"
                v-model="type"
                v-bind="typeAttrs"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.type
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              >
                <option value="rss">RSS Feed</option>
                <option value="youtube">YouTube</option>
                <option value="website">Website</option>
                <option value="blog">Blog</option>
              </select>
              <Transition name="error">
                <p v-if="errors.type" class="mt-2 text-sm text-status-failed">
                  {{ errors.type }}
                </p>
              </Transition>
            </div>

            <!-- URL Field -->
            <div>
              <label for="url" class="mb-2 block text-sm font-medium text-text-primary">
                URL
              </label>
              <input
                id="url"
                v-model="url"
                v-bind="urlAttrs"
                type="url"
                :placeholder="urlPlaceholder"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.url
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.url" class="mt-2 text-sm text-status-failed">
                  {{ errors.url }}
                </p>
              </Transition>
              <!-- YouTube helper text -->
              <p v-if="type === 'youtube'" class="mt-2 text-xs text-text-muted">
                Supports both video URLs (youtube.com/watch?v=...) and channel URLs
                (youtube.com/@channel, youtube.com/channel/UC...). Channels will fetch
                transcripts from recent videos.
              </p>
            </div>

            <!-- Enabled Toggle -->
            <div class="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-surface p-4">
              <div>
                <label for="enabled" class="block text-sm font-medium text-text-primary">
                  Enable Source
                </label>
                <p class="mt-1 text-xs text-text-muted">
                  Disabled sources will not be fetched
                </p>
              </div>
              <button
                type="button"
                @click="enabled = !enabled"
                class="relative inline-flex h-7 w-14 items-center rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                :class="enabled ? 'bg-accent-primary' : 'bg-bg-hover'"
                role="switch"
                :aria-checked="enabled"
              >
                <span
                  class="inline-block h-5 w-5 transform rounded-full bg-white shadow-lg transition-transform duration-300"
                  :class="enabled ? 'translate-x-8' : 'translate-x-1'"
                />
              </button>
            </div>

            <!-- Filters Section -->
            <div class="rounded-lg border border-border-subtle bg-bg-surface">
              <!-- Toggle Header -->
              <button
                type="button"
                @click="showFilters = !showFilters"
                class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-bg-hover"
              >
                <div class="flex items-center gap-2">
                  <Filter :size="18" class="text-text-muted" />
                  <span class="text-sm font-medium text-text-primary">Filters</span>
                  <span v-if="hasFilters" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
                    {{ activeFilterCount }} active
                  </span>
                </div>
                <span class="text-xs text-text-muted">{{ showFilters ? 'Hide' : 'Show' }}</span>
              </button>

              <!-- Filter Content -->
              <Transition name="slide">
                <div v-if="showFilters" class="border-t border-border-subtle p-4 space-y-4">
                  <!-- Max Items -->
                  <div>
                    <label class="mb-2 block text-sm font-medium text-text-primary">
                      Max Items per Run
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      Limit the number of items fetched per run (newest first)
                    </p>
                    <input
                      v-model.number="maxItems"
                      type="number"
                      min="1"
                      max="100"
                      placeholder="No limit"
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
                      Include Keywords
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      Items must match at least one keyword to be processed
                    </p>
                    <div class="flex gap-2">
                      <input
                        v-model="includeInput"
                        type="text"
                        placeholder="Add keyword..."
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
                      Exclude Keywords
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      Items matching any keyword will be skipped
                    </p>
                    <div class="flex gap-2">
                      <input
                        v-model="excludeInput"
                        type="text"
                        placeholder="Add keyword..."
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
                        Search In
                      </label>
                      <select
                        v-model="filterMode"
                        class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                      >
                        <option value="both">Title & Content</option>
                        <option value="title_only">Title Only</option>
                        <option value="content">Content Only</option>
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
                        Regex
                      </button>
                    </div>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- Actions -->
            <div class="flex gap-3 pt-4">
              <button
                type="button"
                @click="handleClose"
                :disabled="isSaving"
                class="flex-1 rounded-lg border border-border-subtle bg-bg-surface px-6 py-3 font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="isSaving"
                class="flex-1 rounded-lg bg-accent-primary px-6 py-3 font-medium text-white transition-all hover:bg-accent-primary-hover disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isSaving"
                  :size="18"
                  class="animate-spin"
                />
                {{ isSaving ? 'Saving...' : (isEditMode ? 'Update' : 'Create') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95) translateY(20px);
  opacity: 0;
}

/* Error message transitions */
.error-enter-active,
.error-leave-active {
  transition: all 0.2s ease;
}

.error-enter-from,
.error-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

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
