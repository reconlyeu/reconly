<script setup lang="ts">
/**
 * Getting Started Wizard
 *
 * A step-by-step wizard that guides new users through:
 * 1. Welcome screen with overview
 * 2. Creating their first source (pre-filled RSS)
 * 3. Creating their first feed
 * 4. Running the feed to generate digests
 *
 * Shows only on first startup (tracked via localStorage).
 * Can be skipped at any step.
 */

import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { sourcesApi, feedsApi, providersApi, promptTemplatesApi, reportTemplatesApi, feedRunsApi } from '@/services/api';
import { useOnboarding } from '@/composables/useOnboarding';
import { useToast } from '@/composables/useToast';
import { useFeedRunPolling } from '@/composables/useFeedRunPolling';
import { strings } from '@/i18n/en';
import type { Source, Feed, FeedRun, PromptTemplate, ReportTemplate } from '@/types/entities';
import {
  X,
  Loader2,
  ChevronRight,
  ChevronLeft,
  Rss,
  Layers,
  Play,
  CheckCircle,
  AlertTriangle,
  Settings,
  ExternalLink,
} from 'lucide-vue-next';

// Get i18n strings for wizard
const t = strings.onboarding.wizard;

const queryClient = useQueryClient();
const toast = useToast();
const { shouldShowWizard, skipOnboarding, finishOnboarding, closeWizard } = useOnboarding();
const { startPolling } = useFeedRunPolling();

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════

const currentStep = ref(1);
const totalSteps = 4;

// Step 2: Source form state
const sourceName = ref(t.steps.source.namePlaceholder);
const sourceUrl = ref(t.steps.source.urlDefault);

// Step 3: Feed form state
const feedName = ref(t.steps.feed.namePlaceholder);

// Created entities
const createdSource = ref<Source | null>(null);
const createdFeed = ref<Feed | null>(null);
const feedRun = ref<FeedRun | null>(null);

// Run status
const isRunning = ref(false);
const runCompleted = ref(false);
const runError = ref<string | null>(null);

// ═══════════════════════════════════════════════════════════════════════════════
// QUERIES
// ═══════════════════════════════════════════════════════════════════════════════

// Check if any LLM provider is configured
const { data: providersData, isLoading: isLoadingProviders } = useQuery({
  queryKey: ['providers'],
  queryFn: () => providersApi.getAll(),
  staleTime: 30000,
});

// Get prompt templates to auto-select one
const { data: promptTemplates } = useQuery({
  queryKey: ['prompt-templates', 'active'],
  queryFn: () => promptTemplatesApi.list(true),
  staleTime: 60000,
});

// Get report templates to auto-select one
const { data: reportTemplates } = useQuery({
  queryKey: ['report-templates', 'active'],
  queryFn: () => reportTemplatesApi.list(true),
  staleTime: 60000,
});

const hasLlmConfigured = computed(() => {
  if (!providersData.value) return false;
  // Check if any provider is available (has models and is ready)
  return providersData.value.providers.some(p => p.is_available && p.models.length > 0);
});

// Get first available prompt template
const defaultPromptTemplate = computed<PromptTemplate | null>(() => {
  if (!promptTemplates.value?.length) return null;
  // Prefer system templates
  const system = promptTemplates.value.find(t => t.is_system);
  return system || promptTemplates.value[0];
});

// Get first available report template
const defaultReportTemplate = computed<ReportTemplate | null>(() => {
  if (!reportTemplates.value?.length) return null;
  // Prefer system templates
  const system = reportTemplates.value.find(t => t.is_system);
  return system || reportTemplates.value[0];
});

// ═══════════════════════════════════════════════════════════════════════════════
// MUTATIONS
// ═══════════════════════════════════════════════════════════════════════════════

// Create source mutation
const createSourceMutation = useMutation({
  mutationFn: async () => {
    return await sourcesApi.create({
      name: sourceName.value,
      url: sourceUrl.value,
      type: 'rss',
      enabled: true,
    });
  },
  onSuccess: (source) => {
    createdSource.value = source;
    queryClient.invalidateQueries({ queryKey: ['sources'] });
    // Advance to next step
    currentStep.value = 3;
  },
  onError: (error: any) => {
    toast.error(error.detail || 'Failed to create source');
  },
});

// Create feed mutation
const createFeedMutation = useMutation({
  mutationFn: async () => {
    if (!createdSource.value) throw new Error('No source created');

    return await feedsApi.create({
      name: feedName.value,
      source_ids: [createdSource.value.id],
      prompt_template_id: defaultPromptTemplate.value?.id,
      report_template_id: defaultReportTemplate.value?.id,
      schedule_enabled: false, // Don't schedule, we'll run manually
    });
  },
  onSuccess: (feed) => {
    createdFeed.value = feed;
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    // Advance to next step
    currentStep.value = 4;
  },
  onError: (error: any) => {
    toast.error(error.detail || 'Failed to create feed');
  },
});

// Run feed mutation
const runFeedMutation = useMutation({
  mutationFn: async () => {
    if (!createdFeed.value) throw new Error('No feed created');
    return await feedsApi.run(createdFeed.value.id);
  },
  onSuccess: async (run) => {
    feedRun.value = run;
    isRunning.value = true;
    runError.value = null;
    // Start polling for completion using shared composable
    startPolling(createdFeed.value!.id, run.id, {
      onComplete: async (completedRun) => {
        // Fetch the full run details
        feedRun.value = await feedRunsApi.get(completedRun.id);
        isRunning.value = false;
        if (completedRun.status === 'completed' || completedRun.status === 'completed_with_errors') {
          runCompleted.value = true;
        } else {
          runError.value = 'Feed run failed. Check your LLM configuration.';
        }
      },
      onError: () => {
        isRunning.value = false;
        runError.value = 'Failed to check run status';
      },
    });
  },
  onError: (error: any) => {
    isRunning.value = false;
    runError.value = error.detail || 'Failed to run feed';
    toast.error(runError.value!);
  },
});

// ═══════════════════════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1:
      return true;
    case 2:
      return sourceName.value.trim() && sourceUrl.value.trim() && !createSourceMutation.isPending.value;
    case 3:
      return feedName.value.trim() && createdSource.value && !createFeedMutation.isPending.value;
    case 4:
      return true;
    default:
      return false;
  }
});

const handleNext = () => {
  switch (currentStep.value) {
    case 1:
      currentStep.value = 2;
      break;
    case 2:
      createSourceMutation.mutate();
      break;
    case 3:
      createFeedMutation.mutate();
      break;
    case 4:
      finishOnboarding();
      break;
  }
};

const handleBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--;
  }
};

const handleSkip = () => {
  skipOnboarding();
};

const handleRunFeed = () => {
  if (createdFeed.value && !isRunning.value && !runCompleted.value) {
    runFeedMutation.mutate();
  }
};

const handleViewResults = () => {
  finishOnboarding();
  // Navigate to digests
  window.location.href = '/digests';
};

const handleGoToSettings = () => {
  finishOnboarding();
  // Navigate to settings providers tab
  window.location.href = '/settings?tab=providers';
};

// Handle escape key
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    handleSkip();
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});

// ═══════════════════════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════════════════════

const stepIndicatorText = computed(() => {
  return t.stepIndicator
    .replace('{current}', String(currentStep.value))
    .replace('{total}', String(totalSteps));
});

const isCreatingSource = computed(() => createSourceMutation.isPending.value);
const isCreatingFeed = computed(() => createFeedMutation.isPending.value);

// Step icons
const stepIcons = [
  { icon: ChevronRight, label: 'Welcome' },
  { icon: Rss, label: 'Source' },
  { icon: Layers, label: 'Feed' },
  { icon: Play, label: 'Run' },
];
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="shouldShowWizard"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        @mousedown.self="handleSkip"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/85 backdrop-blur-md" />

        <!-- Modal -->
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="wizard-title"
          class="relative w-full max-w-xl overflow-hidden rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface shadow-2xl shadow-black/60"
        >
          <!-- Decorative gradient orbs -->
          <div class="pointer-events-none absolute -right-20 -top-20 h-40 w-40 rounded-full bg-accent-primary/20 blur-3xl" />
          <div class="pointer-events-none absolute -left-20 -bottom-20 h-40 w-40 rounded-full bg-accent-secondary/10 blur-3xl" />

          <!-- Header -->
          <div class="relative flex items-center justify-between border-b border-border-subtle p-6">
            <div>
              <h2 id="wizard-title" class="text-2xl font-bold text-text-primary">{{ t.title }}</h2>
              <p class="mt-1 text-sm text-text-muted">{{ t.subtitle }}</p>
            </div>
            <button
              @click="handleSkip"
              class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
              :title="strings.common.close"
            >
              <X :size="20" />
            </button>
          </div>

          <!-- Step Indicator -->
          <div class="border-b border-border-subtle px-6 py-4">
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium text-text-secondary">{{ stepIndicatorText }}</span>
              <div class="flex gap-2">
                <div
                  v-for="(step, index) in stepIcons"
                  :key="index"
                  class="flex h-8 w-8 items-center justify-center rounded-full transition-all"
                  :class="
                    index + 1 <= currentStep
                      ? 'bg-accent-primary text-white'
                      : 'bg-bg-hover text-text-muted'
                  "
                >
                  <component :is="step.icon" :size="16" />
                </div>
              </div>
            </div>
          </div>

          <!-- Content -->
          <div class="relative p-6 min-h-[320px]">
            <!-- Step 1: Welcome -->
            <Transition name="fade" mode="out-in">
              <div v-if="currentStep === 1" key="welcome" class="space-y-6">
                <div class="flex items-center gap-4">
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-accent-primary/10">
                    <Layers class="text-accent-primary" :size="24" />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold text-text-primary">{{ t.steps.welcome.title }}</h3>
                    <p class="text-sm text-text-muted">{{ t.steps.welcome.description }}</p>
                  </div>
                </div>

                <ul class="space-y-3 pl-4">
                  <li
                    v-for="(item, index) in t.steps.welcome.items"
                    :key="index"
                    class="flex items-center gap-3 text-text-secondary"
                  >
                    <span class="flex h-6 w-6 items-center justify-center rounded-full bg-accent-primary/20 text-xs font-semibold text-accent-primary">
                      {{ index + 1 }}
                    </span>
                    {{ item }}
                  </li>
                </ul>

                <!-- LLM Warning -->
                <div
                  v-if="!isLoadingProviders && !hasLlmConfigured"
                  class="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4"
                >
                  <AlertTriangle class="mt-0.5 flex-shrink-0 text-amber-500" :size="18" />
                  <p class="text-sm text-amber-200">{{ t.steps.welcome.llmWarning }}</p>
                </div>
              </div>

              <!-- Step 2: Create Source -->
              <div v-else-if="currentStep === 2" key="source" class="space-y-6">
                <div class="flex items-center gap-4">
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-500/10">
                    <Rss class="text-orange-400" :size="24" />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold text-text-primary">{{ t.steps.source.title }}</h3>
                    <p class="text-sm text-text-muted">{{ t.steps.source.description }}</p>
                  </div>
                </div>

                <div class="space-y-4">
                  <!-- Name -->
                  <div>
                    <label for="source-name" class="mb-2 block text-sm font-medium text-text-primary">
                      {{ t.steps.source.nameLabel }}
                    </label>
                    <input
                      id="source-name"
                      v-model="sourceName"
                      type="text"
                      :placeholder="t.steps.source.namePlaceholder"
                      class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                      :disabled="isCreatingSource"
                    />
                  </div>

                  <!-- URL -->
                  <div>
                    <label for="source-url" class="mb-2 block text-sm font-medium text-text-primary">
                      {{ t.steps.source.urlLabel }}
                    </label>
                    <input
                      id="source-url"
                      v-model="sourceUrl"
                      type="url"
                      :placeholder="t.steps.source.urlDefault"
                      class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base font-mono"
                      :disabled="isCreatingSource"
                    />
                  </div>
                </div>
              </div>

              <!-- Step 3: Create Feed -->
              <div v-else-if="currentStep === 3" key="feed" class="space-y-6">
                <div class="flex items-center gap-4">
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10">
                    <Layers class="text-blue-400" :size="24" />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold text-text-primary">{{ t.steps.feed.title }}</h3>
                    <p class="text-sm text-text-muted">{{ t.steps.feed.description }}</p>
                  </div>
                </div>

                <div class="space-y-4">
                  <!-- Feed Name -->
                  <div>
                    <label for="feed-name" class="mb-2 block text-sm font-medium text-text-primary">
                      {{ t.steps.feed.nameLabel }}
                    </label>
                    <input
                      id="feed-name"
                      v-model="feedName"
                      type="text"
                      :placeholder="t.steps.feed.namePlaceholder"
                      class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                      :disabled="isCreatingFeed"
                    />
                  </div>

                  <!-- Source (auto-selected) -->
                  <div>
                    <label class="mb-2 block text-sm font-medium text-text-primary">
                      {{ t.steps.feed.sourceLabel }}
                    </label>
                    <div class="flex items-center gap-3 rounded-lg border border-border-subtle bg-bg-surface p-4">
                      <Rss class="flex-shrink-0 text-orange-400" :size="18" />
                      <div class="min-w-0 flex-1">
                        <div class="font-medium text-text-primary">{{ createdSource?.name }}</div>
                        <div class="truncate text-xs text-text-muted">{{ createdSource?.url }}</div>
                      </div>
                      <CheckCircle class="flex-shrink-0 text-status-success" :size="18" />
                    </div>
                  </div>
                </div>
              </div>

              <!-- Step 4: Run Feed -->
              <div v-else-if="currentStep === 4" key="run" class="space-y-6">
                <div class="flex items-center gap-4">
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-green-500/10">
                    <Play class="text-green-400" :size="24" />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold text-text-primary">{{ t.steps.run.title }}</h3>
                    <p class="text-sm text-text-muted">
                      {{ runCompleted ? t.steps.run.completed : t.steps.run.description }}
                    </p>
                  </div>
                </div>

                <!-- No LLM Configured -->
                <div v-if="!hasLlmConfigured" class="space-y-4">
                  <div class="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                    <AlertTriangle class="mt-0.5 flex-shrink-0 text-amber-500" :size="18" />
                    <p class="text-sm text-amber-200">{{ t.steps.run.noLlm }}</p>
                  </div>

                  <button
                    @click="handleGoToSettings"
                    class="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-primary px-4 py-3 font-medium text-white transition-colors hover:bg-accent-primary-hover"
                  >
                    <Settings :size="18" />
                    {{ t.steps.run.goToSettings }}
                  </button>
                </div>

                <!-- LLM Configured - Show Run State -->
                <div v-else class="space-y-4">
                  <!-- Run Status -->
                  <div class="rounded-lg border border-border-subtle bg-bg-surface p-6">
                    <!-- Not started -->
                    <div v-if="!isRunning && !runCompleted && !runError" class="text-center">
                      <p class="mb-4 text-text-muted">Ready to generate your first digest</p>
                      <button
                        @click="handleRunFeed"
                        :disabled="runFeedMutation.isPending.value"
                        class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-6 py-3 font-medium text-white transition-colors hover:bg-accent-primary-hover disabled:opacity-50"
                      >
                        <Loader2 v-if="runFeedMutation.isPending.value" class="animate-spin" :size="18" />
                        <Play v-else :size="18" />
                        {{ runFeedMutation.isPending.value ? t.steps.run.running : 'Run Now' }}
                      </button>
                    </div>

                    <!-- Running -->
                    <div v-else-if="isRunning" class="flex flex-col items-center gap-4 py-4">
                      <div class="relative">
                        <Loader2 class="h-12 w-12 animate-spin text-accent-primary" />
                      </div>
                      <p class="text-text-secondary">{{ t.steps.run.running }}</p>
                      <p class="text-xs text-text-muted">This may take a minute...</p>
                    </div>

                    <!-- Completed -->
                    <div v-else-if="runCompleted" class="flex flex-col items-center gap-4 py-4">
                      <div class="flex h-12 w-12 items-center justify-center rounded-full bg-status-success/20">
                        <CheckCircle class="text-status-success" :size="24" />
                      </div>
                      <p class="text-text-primary font-medium">{{ t.steps.run.completed }}</p>
                    </div>

                    <!-- Error -->
                    <div v-else-if="runError" class="flex flex-col items-center gap-4 py-4">
                      <div class="flex h-12 w-12 items-center justify-center rounded-full bg-status-failed/20">
                        <AlertTriangle class="text-status-failed" :size="24" />
                      </div>
                      <p class="text-status-failed">{{ runError }}</p>
                      <button
                        @click="handleRunFeed"
                        class="text-sm text-accent-primary hover:underline"
                      >
                        Try again
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between border-t border-border-subtle p-6">
            <!-- Left: Skip -->
            <button
              @click="handleSkip"
              class="text-sm text-text-muted transition-colors hover:text-text-secondary"
            >
              {{ t.skip }}
            </button>

            <!-- Right: Back / Next -->
            <div class="flex gap-3">
              <button
                v-if="currentStep > 1"
                @click="handleBack"
                :disabled="isCreatingSource || isCreatingFeed || isRunning"
                class="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-50"
              >
                <ChevronLeft :size="16" />
                {{ t.back }}
              </button>

              <!-- Step 4 has special buttons -->
              <template v-if="currentStep === 4">
                <button
                  v-if="runCompleted"
                  @click="handleViewResults"
                  class="flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-primary-hover"
                >
                  {{ t.steps.run.viewResults }}
                  <ExternalLink :size="16" />
                </button>
                <button
                  v-else-if="!hasLlmConfigured"
                  @click="handleSkip"
                  class="flex items-center gap-2 rounded-lg bg-bg-hover px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-surface"
                >
                  {{ t.steps.welcome.skip }}
                </button>
              </template>

              <!-- Other steps -->
              <template v-else>
                <button
                  v-if="currentStep === 1"
                  @click="handleNext"
                  class="flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-primary-hover"
                >
                  {{ t.steps.welcome.start }}
                  <ChevronRight :size="16" />
                </button>
                <button
                  v-else
                  @click="handleNext"
                  :disabled="!canProceed"
                  class="flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-primary-hover disabled:opacity-50"
                >
                  <Loader2 v-if="isCreatingSource || isCreatingFeed" class="animate-spin" :size="16" />
                  <template v-if="currentStep === 2">
                    {{ isCreatingSource ? t.steps.source.creating : t.steps.source.create }}
                  </template>
                  <template v-else-if="currentStep === 3">
                    {{ isCreatingFeed ? t.steps.feed.creating : t.steps.feed.create }}
                  </template>
                  <ChevronRight v-if="!isCreatingSource && !isCreatingFeed" :size="16" />
                </button>
              </template>
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
  transform: scale(0.95) translateY(20px);
  opacity: 0;
}

/* Fade transitions for step content */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
