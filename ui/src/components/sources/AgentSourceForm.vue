<script setup lang="ts">
/**
 * Agent source configuration form component.
 * Used within SourceForm for agent-type sources.
 * Provides inputs for research prompt, strategy selection, and max iterations.
 */
import { ref, computed, onMounted, watch } from 'vue';
import type { SourceConfig, AgentCapabilities, ResearchStrategy, ResearchReportFormat } from '@/types/entities';
import { agentRunsApi } from '@/services/api';
import { Clock, AlertTriangle, Info } from 'lucide-vue-next';

const config = defineModel<SourceConfig>('config', { default: () => ({}) });
const prompt = defineModel<string>('prompt', { required: true });

// Capabilities state
const capabilities = ref<AgentCapabilities | null>(null);
const capabilitiesLoading = ref(true);
const capabilitiesError = ref<string | null>(null);

// Fetch capabilities on mount
onMounted(async () => {
  try {
    capabilities.value = await agentRunsApi.getCapabilities();
  } catch (error) {
    capabilitiesError.value = 'Could not load agent capabilities';
    console.error('Failed to load agent capabilities:', error);
  } finally {
    capabilitiesLoading.value = false;
  }
});

// Format duration for display
const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `~${seconds}s`;
  const mins = Math.floor(seconds / 60);
  return `~${mins}min`;
};

// Get strategy info
const getStrategyInfo = (strategy: ResearchStrategy) => {
  if (!capabilities.value) return null;
  return capabilities.value.strategies[strategy];
};

// Check if strategy is available
const isStrategyAvailable = (strategy: ResearchStrategy): boolean => {
  const info = getStrategyInfo(strategy);
  return info?.available ?? false;
};

// Check if advanced strategies require gpt-researcher
const needsGptResearcher = computed(() => {
  return !capabilities.value?.gpt_researcher_installed;
});

// Check if comprehensive/deep is selected
const isAdvancedStrategy = computed(() => {
  return config.value.research_strategy === 'comprehensive' || config.value.research_strategy === 'deep';
});

// Reset advanced options when switching to simple
watch(() => config.value.research_strategy, (newStrategy) => {
  if (newStrategy === 'simple') {
    // Clear advanced options when switching to simple
    config.value.report_format = undefined;
    config.value.max_subtopics = undefined;
  }
});

// Report format options
const reportFormats: { value: ResearchReportFormat; label: string }[] = [
  { value: 'APA', label: 'APA (American Psychological Association)' },
  { value: 'MLA', label: 'MLA (Modern Language Association)' },
  { value: 'CMS', label: 'CMS (Chicago Manual of Style)' },
  { value: 'Harvard', label: 'Harvard Referencing' },
  { value: 'IEEE', label: 'IEEE (Institute of Electrical and Electronics Engineers)' },
];
</script>

<template>
  <div class="space-y-4">
    <!-- Prompt (research topic) -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        Research Topic
      </label>
      <p class="mb-2 text-xs text-text-muted">
        Describe what the AI agent should research. Be specific for better results.
      </p>
      <textarea
        v-model="prompt"
        placeholder="Research the latest developments in AI language models..."
        class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        rows="4"
      />
    </div>

    <!-- Research Strategy -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        Research Strategy
      </label>
      <p class="mb-2 text-xs text-text-muted">
        Choose how thoroughly the agent should research the topic
      </p>

      <!-- Loading state -->
      <div v-if="capabilitiesLoading" class="animate-pulse rounded-lg border border-border-subtle bg-bg-surface p-4">
        <div class="h-4 w-48 rounded bg-bg-hover"></div>
      </div>

      <!-- Error state -->
      <div v-else-if="capabilitiesError" class="rounded-lg border border-border-subtle bg-bg-surface p-4">
        <p class="text-sm text-text-muted">{{ capabilitiesError }}</p>
        <p class="mt-1 text-xs text-text-muted">Using default options</p>
        <select
          v-model="config.research_strategy"
          class="mt-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
        >
          <option :value="undefined">Simple (default)</option>
          <option value="simple">Simple</option>
          <option value="comprehensive">Comprehensive</option>
          <option value="deep">Deep</option>
        </select>
      </div>

      <!-- Strategy selector cards -->
      <div v-else class="space-y-2">
        <!-- Simple Strategy -->
        <label
          class="flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-all"
          :class="[
            config.research_strategy === 'simple' || !config.research_strategy
              ? 'border-accent-primary bg-accent-primary/5'
              : 'border-border-subtle bg-bg-surface hover:border-border-default',
          ]"
        >
          <input
            type="radio"
            :value="'simple'"
            v-model="config.research_strategy"
            class="mt-1 h-4 w-4 border-border-subtle text-accent-primary focus:ring-accent-primary"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium text-text-primary">Simple</span>
              <span
                v-if="getStrategyInfo('simple')"
                class="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted"
                :title="`Estimated time: ${formatDuration(getStrategyInfo('simple')!.estimated_duration_seconds)}`"
              >
                <Clock :size="12" />
                {{ formatDuration(getStrategyInfo('simple')!.estimated_duration_seconds) }}
              </span>
            </div>
            <p class="mt-1 text-sm text-text-muted">
              {{ getStrategyInfo('simple')?.description || 'Quick lookup using search and summarization' }}
            </p>
          </div>
        </label>

        <!-- Comprehensive Strategy -->
        <label
          class="flex items-start gap-3 rounded-lg border p-4 transition-all"
          :class="[
            !isStrategyAvailable('comprehensive')
              ? 'cursor-not-allowed opacity-60 border-border-subtle bg-bg-surface'
              : config.research_strategy === 'comprehensive'
                ? 'cursor-pointer border-accent-primary bg-accent-primary/5'
                : 'cursor-pointer border-border-subtle bg-bg-surface hover:border-border-default',
          ]"
        >
          <input
            type="radio"
            value="comprehensive"
            v-model="config.research_strategy"
            :disabled="!isStrategyAvailable('comprehensive')"
            class="mt-1 h-4 w-4 border-border-subtle text-accent-primary focus:ring-accent-primary disabled:opacity-50"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium text-text-primary">Comprehensive</span>
              <span
                v-if="getStrategyInfo('comprehensive')"
                class="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted"
                :title="`Estimated time: ${formatDuration(getStrategyInfo('comprehensive')!.estimated_duration_seconds)}`"
              >
                <Clock :size="12" />
                {{ formatDuration(getStrategyInfo('comprehensive')!.estimated_duration_seconds) }}
              </span>
              <span
                v-if="!isStrategyAvailable('comprehensive')"
                class="inline-flex items-center gap-1 rounded-full bg-status-failed/10 px-2 py-0.5 text-xs text-status-failed"
              >
                Unavailable
              </span>
            </div>
            <p class="mt-1 text-sm text-text-muted">
              {{ getStrategyInfo('comprehensive')?.description || 'Multi-step research with subtopic exploration' }}
            </p>
          </div>
        </label>

        <!-- Deep Strategy -->
        <label
          class="flex items-start gap-3 rounded-lg border p-4 transition-all"
          :class="[
            !isStrategyAvailable('deep')
              ? 'cursor-not-allowed opacity-60 border-border-subtle bg-bg-surface'
              : config.research_strategy === 'deep'
                ? 'cursor-pointer border-accent-primary bg-accent-primary/5'
                : 'cursor-pointer border-border-subtle bg-bg-surface hover:border-border-default',
          ]"
        >
          <input
            type="radio"
            value="deep"
            v-model="config.research_strategy"
            :disabled="!isStrategyAvailable('deep')"
            class="mt-1 h-4 w-4 border-border-subtle text-accent-primary focus:ring-accent-primary disabled:opacity-50"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium text-text-primary">Deep</span>
              <span
                v-if="getStrategyInfo('deep')"
                class="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted"
                :title="`Estimated time: ${formatDuration(getStrategyInfo('deep')!.estimated_duration_seconds)}`"
              >
                <Clock :size="12" />
                {{ formatDuration(getStrategyInfo('deep')!.estimated_duration_seconds) }}
              </span>
              <span
                v-if="!isStrategyAvailable('deep')"
                class="inline-flex items-center gap-1 rounded-full bg-status-failed/10 px-2 py-0.5 text-xs text-status-failed"
              >
                Unavailable
              </span>
            </div>
            <p class="mt-1 text-sm text-text-muted">
              {{ getStrategyInfo('deep')?.description || 'Exhaustive analysis with detailed research plan' }}
            </p>
          </div>
        </label>

        <!-- Warning if gpt-researcher not installed -->
        <div
          v-if="needsGptResearcher"
          class="mt-3 flex items-start gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3"
        >
          <AlertTriangle :size="16" class="mt-0.5 flex-shrink-0 text-yellow-500" />
          <div>
            <p class="text-sm font-medium text-yellow-500">GPT Researcher not installed</p>
            <p class="mt-0.5 text-xs text-text-muted">
              Comprehensive and Deep strategies require the gpt-researcher package.
              Install with: <code class="rounded bg-bg-hover px-1 py-0.5 text-xs">pip install gpt-researcher</code>
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Advanced Options (for comprehensive/deep) -->
    <div v-if="isAdvancedStrategy && !capabilitiesLoading" class="space-y-4 rounded-lg border border-border-subtle bg-bg-surface/50 p-4">
      <h4 class="flex items-center gap-2 text-sm font-medium text-text-primary">
        <Info :size="14" class="text-text-muted" />
        Advanced Options
      </h4>

      <!-- Report Format -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          Report Format
        </label>
        <p class="mb-2 text-xs text-text-muted">
          Citation style for the research report
        </p>
        <select
          v-model="config.report_format"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
        >
          <option :value="undefined">Default (APA)</option>
          <option v-for="format in reportFormats" :key="format.value" :value="format.value">
            {{ format.label }}
          </option>
        </select>
      </div>

      <!-- Max Subtopics -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          Max Subtopics
        </label>
        <p class="mb-2 text-xs text-text-muted">
          Maximum number of subtopics to explore (1-10)
        </p>
        <div class="flex items-center gap-4">
          <input
            type="range"
            v-model.number="config.max_subtopics"
            min="1"
            max="10"
            class="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-bg-hover accent-accent-primary"
          />
          <span class="w-8 text-center text-sm font-medium text-text-primary">
            {{ config.max_subtopics || 5 }}
          </span>
        </div>
      </div>
    </div>

    <!-- Max Iterations -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        Max Research Iterations
      </label>
      <p class="mb-2 text-xs text-text-muted">
        How many search and fetch cycles the agent can perform (default: 5)
      </p>
      <select
        v-model.number="config.max_iterations"
        class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
      >
        <option :value="undefined">Default (5)</option>
        <option v-for="n in 10" :key="n" :value="n">{{ n }}</option>
      </select>
    </div>

    <!-- Search Provider Override -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        Search Provider
      </label>
      <p class="mb-2 text-xs text-text-muted">
        Override the global search provider for this source (optional)
      </p>
      <select
        v-model="config.search_provider"
        class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
      >
        <option :value="undefined">Default (global setting)</option>
        <option value="duckduckgo">DuckDuckGo (free, no API key)</option>
        <option value="searxng">SearXNG (self-hosted)</option>
        <option value="tavily">Tavily (AI-optimized, requires API key)</option>
      </select>

      <!-- Provider hints -->
      <p v-if="config.search_provider === 'tavily'" class="mt-2 text-xs text-accent-primary">
        Note: Requires TAVILY_API_KEY environment variable
      </p>
      <p v-if="config.search_provider === 'searxng'" class="mt-2 text-xs text-text-muted">
        Note: Requires SearXNG instance configured via SEARXNG_URL
      </p>
    </div>
  </div>
</template>
