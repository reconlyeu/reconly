<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import {
  Database,
  ListTree,
  FileText,
} from 'lucide-vue-next';
import StatsWidget from './StatsWidget.vue';
import { dashboardApi } from '@/services/api';
import { strings } from '@/i18n/en';

const { data: stats, isLoading } = useQuery({
  queryKey: ['dashboard-stats'],
  queryFn: dashboardApi.getStats,
  refetchInterval: 30000, // Refresh every 30 seconds
});

const statsConfig = computed(() => [
  {
    label: strings.dashboard.stats.sources,
    value: stats.value?.sources_count ?? '-',
    icon: Database,
    variant: 'default' as const,
    delay: '0ms',
    href: '/sources',
  },
  {
    label: strings.dashboard.stats.feeds,
    value: stats.value?.feeds_count ?? '-',
    icon: ListTree,
    variant: 'primary' as const,
    delay: '100ms',
    href: '/feeds',
  },
  {
    label: strings.dashboard.stats.digests,
    value: stats.value?.digests_count ?? '-',
    icon: FileText,
    variant: 'default' as const,
    delay: '200ms',
    href: '/digests',
  },
]);
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <StatsWidget
      v-for="(stat, index) in statsConfig"
      :key="stat.label"
      :label="stat.label"
      :value="stat.value"
      :icon="stat.icon"
      :variant="stat.variant"
      :loading="isLoading"
      :href="stat.href"
      :style="{ animationDelay: stat.delay }"
    />
  </div>
</template>


