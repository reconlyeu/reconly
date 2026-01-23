<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useMutation } from '@tanstack/vue-query';
import { X, Upload, FileText, AlertTriangle, CheckCircle2, AlertCircle, Rss, FileCode, Calendar, Loader2 } from 'lucide-vue-next';
import { bundlesApi } from '@/services/api';
import type { BundlePreviewResponse, BundleImportResponse, FeedBundle } from '@/types/entities';
import { useToast } from '@/composables/useToast';
import { strings } from '@/i18n/en';

interface Props {
  show: boolean;
}

interface Emits {
  (e: 'close'): void;
  (e: 'success', result: BundleImportResponse): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const toast = useToast();

// State
const step = ref<'upload' | 'preview' | 'importing'>('upload');
const bundleJson = ref<Record<string, unknown> | null>(null);
const preview = ref<BundlePreviewResponse | null>(null);
const isDragging = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);
const parseError = ref<string | null>(null);

// Reset state when modal closes
watch(() => props.show, (isOpen) => {
  if (!isOpen) {
    step.value = 'upload';
    bundleJson.value = null;
    preview.value = null;
    parseError.value = null;
    isDragging.value = false;
  }
});

// Preview mutation
const previewMutation = useMutation({
  mutationFn: (bundle: Record<string, unknown>) => bundlesApi.preview(bundle),
  onSuccess: (result) => {
    preview.value = result;
    step.value = 'preview';
  },
  onError: (error: any) => {
    parseError.value = error.detail || error.message || 'Failed to preview bundle';
  },
});

// Import mutation
const importMutation = useMutation({
  mutationFn: (bundle: Record<string, unknown>) => bundlesApi.import(bundle, true),
  onSuccess: (result) => {
    if (result.success) {
      toast.success(`Feed "${result.feed_name}" imported successfully`);
      emit('success', result);
    } else {
      toast.error(`Import failed: ${result.errors.join(', ')}`);
      step.value = 'preview'; // Go back to preview
    }
  },
  onError: (error: any) => {
    toast.error(`Import failed: ${error.detail || error.message || 'Unknown error'}`);
    step.value = 'preview'; // Go back to preview
  },
});

// File handling
const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    processFile(input.files[0]);
  }
};

const handleDrop = (event: DragEvent) => {
  event.preventDefault();
  isDragging.value = false;

  const files = event.dataTransfer?.files;
  if (files && files.length > 0) {
    processFile(files[0]);
  }
};

const handleDragOver = (event: DragEvent) => {
  event.preventDefault();
  isDragging.value = true;
};

const handleDragLeave = () => {
  isDragging.value = false;
};

const processFile = async (file: File) => {
  parseError.value = null;

  if (!file.name.endsWith('.json')) {
    parseError.value = strings.feeds.import.errors.selectJson;
    return;
  }

  try {
    const text = await file.text();
    const data = JSON.parse(text);
    bundleJson.value = data;
    previewMutation.mutate(data);
  } catch (e) {
    parseError.value = strings.feeds.import.errors.invalidJson;
  }
};

const triggerFileInput = () => {
  fileInputRef.value?.click();
};

// Import action
const handleImport = () => {
  if (bundleJson.value) {
    step.value = 'importing';
    importMutation.mutate(bundleJson.value);
  }
};

// Computed properties
const hasErrors = computed(() => {
  return preview.value && preview.value.errors.length > 0;
});

const hasWarnings = computed(() => {
  return preview.value && preview.value.warnings.length > 0;
});

const canImport = computed(() => {
  return preview.value && preview.value.valid && !preview.value.feed?.already_exists;
});

const feedAlreadyExists = computed(() => {
  return preview.value?.feed?.already_exists;
});
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="emit('close')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/90 backdrop-blur-md" />

        <!-- Modal -->
        <div
          class="modal-content relative w-full max-w-xl max-h-[90vh] overflow-y-auto overflow-x-hidden rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-base shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orbs -->
          <div class="pointer-events-none absolute -right-40 -top-40 h-96 w-96 rounded-full bg-accent-primary/10 blur-3xl" />
          <div class="pointer-events-none absolute -left-40 -bottom-40 h-96 w-96 rounded-full bg-purple-500/10 blur-3xl" />

          <!-- Header -->
          <div class="relative border-b border-border-subtle p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-primary/10">
                  <Upload :size="20" class="text-accent-primary" :stroke-width="2" />
                </div>
                <h2 class="text-xl font-semibold text-text-primary">{{ strings.feeds.import.title }}</h2>
              </div>
              <button
                @click="emit('close')"
                class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
              >
                <X :size="20" />
              </button>
            </div>
          </div>

          <!-- Content -->
          <div class="relative p-6">
            <!-- Upload Step -->
            <div v-if="step === 'upload'">
              <p class="mb-4 text-sm text-text-secondary">
                {{ strings.feeds.import.description }}
              </p>

              <!-- Drop Zone -->
              <div
                class="mb-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all"
                :class="isDragging
                  ? 'border-accent-primary bg-accent-primary/5'
                  : 'border-border-default hover:border-accent-primary/50 hover:bg-bg-hover/50'
                "
                @click="triggerFileInput"
                @drop="handleDrop"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
              >
                <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-bg-hover">
                  <FileText :size="24" class="text-text-muted" :stroke-width="2" />
                </div>
                <p class="mb-1 text-sm font-medium text-text-primary">
                  {{ strings.feeds.import.dropZone.title }}
                </p>
                <p class="text-xs text-text-muted">
                  {{ strings.feeds.import.dropZone.subtitle }}
                </p>
              </div>

              <input
                ref="fileInputRef"
                type="file"
                accept=".json"
                class="hidden"
                @change="handleFileSelect"
              />

              <!-- Parse Error -->
              <div v-if="parseError" class="rounded-lg bg-status-failed/10 p-4">
                <div class="flex items-start gap-3">
                  <AlertCircle :size="20" class="mt-0.5 text-status-failed" :stroke-width="2" />
                  <div>
                    <p class="font-medium text-status-failed">{{ strings.feeds.import.errors.title }}</p>
                    <p class="text-sm text-status-failed/80">{{ parseError }}</p>
                  </div>
                </div>
              </div>

              <!-- Loading -->
              <div v-if="previewMutation.isPending.value" class="flex items-center justify-center py-4">
                <Loader2 :size="24" class="animate-spin text-accent-primary" :stroke-width="2" />
                <span class="ml-2 text-sm text-text-secondary">{{ strings.feeds.import.validating }}</span>
              </div>
            </div>

            <!-- Preview Step -->
            <div v-else-if="step === 'preview' && preview">
              <!-- Feed Info -->
              <div class="mb-4 rounded-lg bg-bg-surface p-4">
                <div class="mb-2 flex items-center gap-2">
                  <Rss :size="18" class="text-accent-primary" :stroke-width="2" />
                  <h3 class="font-semibold text-text-primary">{{ preview.feed?.name }}</h3>
                  <span class="rounded-full bg-accent-primary/10 px-2 py-0.5 text-xs text-accent-primary">
                    v{{ preview.feed?.version }}
                  </span>
                </div>
                <p v-if="preview.feed?.description" class="text-sm text-text-secondary">
                  {{ preview.feed?.description }}
                </p>
              </div>

              <!-- Errors -->
              <div v-if="hasErrors" class="mb-4 rounded-lg bg-status-failed/10 p-4">
                <div class="mb-2 flex items-center gap-2">
                  <AlertCircle :size="18" class="text-status-failed" :stroke-width="2" />
                  <span class="font-medium text-status-failed">{{ strings.feeds.import.preview.errors }}</span>
                </div>
                <ul class="list-inside list-disc text-sm text-status-failed/80">
                  <li v-for="error in preview.errors" :key="error">{{ error }}</li>
                </ul>
              </div>

              <!-- Feed Already Exists Warning -->
              <div v-if="feedAlreadyExists" class="mb-4 rounded-lg bg-status-warning/10 p-4">
                <div class="flex items-start gap-3">
                  <AlertTriangle :size="18" class="mt-0.5 text-status-warning" :stroke-width="2" />
                  <div>
                    <p class="font-medium text-status-warning">{{ strings.feeds.import.preview.feedExists.title }}</p>
                    <p class="text-sm text-status-warning/80">
                      {{ strings.feeds.import.preview.feedExists.message.replace('{name}', preview.feed?.name || '') }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- Warnings -->
              <div v-if="hasWarnings && !feedAlreadyExists" class="mb-4 rounded-lg bg-status-warning/10 p-4">
                <div class="mb-2 flex items-center gap-2">
                  <AlertTriangle :size="18" class="text-status-warning" :stroke-width="2" />
                  <span class="font-medium text-status-warning">{{ strings.feeds.import.preview.warnings }}</span>
                </div>
                <ul class="list-inside list-disc text-sm text-status-warning/80">
                  <li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>

              <!-- What will be created -->
              <div class="mb-4 rounded-lg border border-border-subtle p-4">
                <h4 class="mb-3 text-sm font-semibold uppercase tracking-wider text-text-muted">
                  {{ strings.feeds.import.preview.willBeCreated }}
                </h4>
                <div class="space-y-2">
                  <!-- Sources -->
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <Rss :size="16" class="text-blue-400" :stroke-width="2" />
                      <span class="text-sm text-text-secondary">{{ strings.feeds.import.preview.sources }}</span>
                    </div>
                    <span class="text-sm font-medium text-text-primary">
                      {{ preview.sources?.new.length || 0 }} {{ strings.feeds.import.preview.new }}
                      <span v-if="preview.sources?.existing.length" class="text-text-muted">
                        ({{ preview.sources?.existing.length }} {{ strings.feeds.import.preview.existing }})
                      </span>
                    </span>
                  </div>

                  <!-- Prompt Template -->
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <FileCode :size="16" class="text-purple-400" :stroke-width="2" />
                      <span class="text-sm text-text-secondary">{{ strings.feeds.import.preview.promptTemplate }}</span>
                    </div>
                    <span class="text-sm text-text-primary">
                      <CheckCircle2 v-if="preview.prompt_template?.included" :size="16" class="text-status-success" :stroke-width="2" />
                      <span v-else class="text-text-muted">{{ strings.feeds.import.preview.none }}</span>
                    </span>
                  </div>

                  <!-- Report Template -->
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <FileText :size="16" class="text-orange-400" :stroke-width="2" />
                      <span class="text-sm text-text-secondary">{{ strings.feeds.import.preview.reportTemplate }}</span>
                    </div>
                    <span class="text-sm text-text-primary">
                      <CheckCircle2 v-if="preview.report_template?.included" :size="16" class="text-status-success" :stroke-width="2" />
                      <span v-else class="text-text-muted">{{ strings.feeds.import.preview.none }}</span>
                    </span>
                  </div>

                  <!-- Schedule -->
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <Calendar :size="16" class="text-green-400" :stroke-width="2" />
                      <span class="text-sm text-text-secondary">{{ strings.feeds.import.preview.schedule }}</span>
                    </div>
                    <span class="text-sm text-text-primary">
                      <template v-if="preview.schedule?.included">
                        {{ preview.schedule?.cron }}
                      </template>
                      <span v-else class="text-text-muted">{{ strings.feeds.import.preview.none }}</span>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Actions -->
              <div class="flex justify-end gap-3">
                <button
                  @click="step = 'upload'; bundleJson = null; preview = null"
                  class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                >
                  {{ strings.feeds.import.actions.back }}
                </button>
                <button
                  @click="handleImport"
                  :disabled="!canImport"
                  class="rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {{ strings.feeds.import.actions.import }}
                </button>
              </div>
            </div>

            <!-- Importing Step -->
            <div v-else-if="step === 'importing'" class="flex flex-col items-center justify-center py-8">
              <Loader2 :size="32" class="animate-spin text-accent-primary" :stroke-width="2" />
              <p class="mt-4 text-text-secondary">{{ strings.feeds.import.importing }}</p>
            </div>
          </div>
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
  transform: scale(0.98) translateY(20px);
  opacity: 0;
}

/* Hide scrollbars but allow scrolling */
.modal-content {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.modal-content::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}
</style>
