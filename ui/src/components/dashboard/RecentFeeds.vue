<script setup lang="ts">
/**
 * RecentFeeds - Shows feeds ordered by last run time
 * Uses a card design similar to FeedCard from /feeds page
 */
import { useQuery } from '@tanstack/vue-query';
import { Rss, CheckCircle2, Calendar, ChevronRight } from 'lucide-vue-next';
import { dashboardApi } from '@/services/api';
import cronstrue from 'cronstrue';
import BaseCard from '@/components/common/BaseCard.vue';

// Props
interface Props {
  limit?: number;
}
const props = withDefaults(defineProps<Props>(), {
  limit: 6,
});

const { data: feeds, isLoading } = useQuery({
  queryKey: ['recent-feeds'],
  queryFn: () => dashboardApi.getRecentFeedsFiltered('all', props.limit),
  refetchInterval: 30000,
});

function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

function formatSchedule(cron: string | null): string {
  if (!cron) return 'No schedule';
  try {
    return cronstrue.toString(cron);
  } catch {
    return cron;
  }
}
</script>

<template>
  <div class="space-y-3">
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 4"
        :key="i"
        class="h-28 animate-pulse rounded-xl bg-bg-elevated"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!feeds || feeds.length === 0"
      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-surface/50 py-12"
    >
      <Rss class="mb-3 h-12 w-12 text-text-muted opacity-50" />
      <p class="text-sm text-text-muted">No feeds run recently</p>
    </div>

    <!-- Feeds list -->
    <div v-else class="space-y-3">
      <a
        v-for="(feed, index) in feeds"
        :key="feed.id"
        :href="`/feeds?edit=${feed.id}`"
        class="group block animate-slide-in-right-fast"
        :style="{ animationDelay: `${index * 50}ms` }"
      >
        <BaseCard glow-color="primary" clickable>
          <div class="flex items-center justify-between gap-3 min-h-14">
            <!-- Left: Feed info -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 mb-2">
                <h4 class="truncate font-semibold text-text-primary group-hover:text-accent-primary transition-colors">
                  {{ feed.name }}
                </h4>
                <div
                  class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="
                    feed.schedule_enabled
                      ? 'bg-status-success/10 text-status-success'
                      : 'bg-text-muted/10 text-text-muted'
                  "
                >
                  {{ feed.schedule_enabled ? 'Active' : 'Paused' }}
                </div>
              </div>

              <!-- Metadata row -->
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
                <!-- Last run -->
                <div class="flex items-center gap-1">
                  <CheckCircle2 class="h-3.5 w-3.5 text-status-success" />
                  <span>{{ formatRelativeTime(feed.last_run_at) }}</span>
                </div>
                <!-- Sources -->
                <div class="flex items-center gap-1">
                  <Rss class="h-3.5 w-3.5" />
                  <span>{{ feed.feed_sources?.length || 0 }} source{{ (feed.feed_sources?.length || 0) !== 1 ? 's' : '' }}</span>
                </div>
                <!-- Schedule -->
                <div v-if="feed.schedule_cron" class="flex items-center gap-1">
                  <Calendar class="h-3.5 w-3.5" />
                  <span class="truncate max-w-[120px]">{{ formatSchedule(feed.schedule_cron) }}</span>
                </div>
              </div>
            </div>

            <!-- Right: Arrow -->
            <ChevronRight
              class="h-5 w-5 shrink-0 text-text-muted opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100"
            />
          </div>
        </BaseCard>
      </a>
    </div>
  </div>
</template>
