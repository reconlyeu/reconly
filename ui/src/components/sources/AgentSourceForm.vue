<script setup lang="ts">
/**
 * Agent source configuration form component.
 * Used within SourceForm for agent-type sources.
 * Provides inputs for research prompt and max iterations.
 */
import { defineModel } from 'vue';
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
  </div>
</template>
