<script setup lang="ts">
/**
 * Agent Run List component.
 * Displays a list of agent runs for a specific source.
 * Uses AgentRunCard for each run item.
 */
import { ref, watch, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { agentRunsApi } from '@/services/api';
import type { AgentRun, AgentRunStatus } from '@/types/entities';
import { Loader2, RefreshCw, Bot } from 'lucide-vue-next';
import AgentRunCard from './AgentRunCard.vue';
import AgentRunModal from './AgentRunModal.vue';
import EmptyState from '@/components/common/EmptyState.vue';

interface Props {
  sourceId: number;
  sourceName?: string;
}

const props = defineProps<Props>();

// Selected run for modal
const selectedRun = ref<AgentRun | null>(null);
const isModalOpen = ref(false);

// Fetch agent runs
const { data, isLoading, isError, refetch, isFetching } = useQuery({
  queryKey: ['agent-runs', props.sourceId],
  queryFn: () => agentRunsApi.list({ source_id: props.sourceId }, 50, 0),
  refetchInterval: 10000, // Refetch every 10 seconds to show running status updates
});

const runs = computed(() => data.value?.items || []);
const total = computed(() => data.value?.total || 0);

// Open run detail modal
const openRunDetail = (run: AgentRun) => {
  selectedRun.value = run;
  isModalOpen.value = true;
};

// Close modal
const closeModal = () => {
  isModalOpen.value = false;
  selectedRun.value = null;
};
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Bot :size="20" class="text-accent-primary" />
        <h3 class="text-lg font-semibold text-text-primary">
          Agent Run History
        </h3>
        <span v-if="total > 0" class="rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted">
          {{ total }} runs
        </span>
      </div>
      <button
        @click="() => refetch()"
        :disabled="isFetching"
        class="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-bg-hover disabled:opacity-50"
      >
        <RefreshCw :size="14" :class="isFetching ? 'animate-spin' : ''" />
        Refresh
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <Loader2 :size="32" class="animate-spin text-accent-primary" />
    </div>

    <!-- Error State -->
    <div v-else-if="isError" class="rounded-lg bg-status-failed/10 p-4 text-center text-status-failed">
      Failed to load agent runs. Please try again.
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="runs.length === 0"
      title="No agent runs yet"
      message="This agent source hasn't been run yet. Add it to a feed and run the feed to see results here."
      :icon="Bot"
    />

    <!-- Run List -->
    <div v-else class="space-y-3">
      <AgentRunCard
        v-for="run in runs"
        :key="run.id"
        :run="run"
        @click="openRunDetail(run)"
      />
    </div>

    <!-- Detail Modal -->
    <AgentRunModal
      :is-open="isModalOpen"
      :run="selectedRun"
      @close="closeModal"
    />
  </div>
</template>
