<script setup lang="ts">
/**
 * Agent source configuration form component.
 * Used within SourceForm for agent-type sources.
 * Provides inputs for research prompt and max iterations.
 */
import type { SourceConfig } from '@/types/entities';

const config = defineModel<SourceConfig>('config', { default: () => ({}) });
const prompt = defineModel<string>('prompt', { required: true });
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
