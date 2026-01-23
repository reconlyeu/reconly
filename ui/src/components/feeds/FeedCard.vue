<script setup lang="ts">
import { computed } from 'vue';
import { Calendar, Clock, PlayCircle, Edit, Trash2, CheckCircle2, Download } from 'lucide-vue-next';
import type { Feed } from '@/types/entities';
import cronstrue from 'cronstrue';
import BaseCard from '@/components/common/BaseCard.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import { strings } from '@/i18n/en';

interface Props {
  feed: Feed;
  isRunning?: boolean;
}

interface Emits {
  (e: 'run', feedId: number): void;
  (e: 'toggle', feedId: number, enabled: boolean): void;
  (e: 'edit', feed: Feed): void;
  (e: 'delete', feedId: number): void;
  (e: 'export', feedId: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const handleToggle = (value: boolean) => {
  emit('toggle', props.feed.id, value);
};

const sourceCount = computed(() => props.feed.feed_sources?.length || 0);

const scheduleText = computed(() => {
  if (!props.feed.schedule_cron) return strings.feeds.schedulePresets.noScheduleSet;
  try {
    return cronstrue.toString(props.feed.schedule_cron);
  } catch {
    return props.feed.schedule_cron;
  }
});

const lastRunConfig = computed(() => {
  if (!props.feed.last_run_at) {
    return { text: strings.feeds.status.neverRun, icon: Clock, color: 'text-text-muted' };
  }

  const date = new Date(props.feed.last_run_at);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  let timeText = '';
  if (diffMins < 1) timeText = strings.time.justNow;
  else if (diffMins < 60) timeText = strings.time.minutesAgo.replace('{count}', String(diffMins));
  else if (diffHours < 24) timeText = strings.time.hoursAgo.replace('{count}', String(diffHours));
  else timeText = date.toLocaleDateString();

  return { text: timeText, icon: CheckCircle2, color: 'text-status-success' };
});
</script>

<template>
  <BaseCard glow-color="primary">
    <template #header>
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <h3 class="mb-1 text-lg font-semibold text-text-primary transition-colors duration-300 group-hover:text-accent-primary">
            {{ feed.name }}
          </h3>
          <p v-if="feed.description" class="text-sm text-text-muted line-clamp-2">
            {{ feed.description }}
          </p>
        </div>

        <!-- Status Badge -->
        <div
          class="ml-4 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-300"
          :class="
            feed.schedule_enabled
              ? 'bg-status-success/10 text-status-success'
              : 'bg-text-muted/10 text-text-muted'
          "
        >
          {{ feed.schedule_enabled ? strings.feeds.status.active : strings.feeds.status.paused }}
        </div>
      </div>
    </template>

    <!-- Metadata Grid -->
    <div class="grid gap-3">
      <!-- Sources Count -->
      <div class="flex items-center gap-2 text-sm">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
          <div class="text-xs font-bold text-blue-400">{{ sourceCount }}</div>
        </div>
        <span class="text-text-secondary">
          {{ sourceCount === 1 ? strings.feeds.sourceUnit : strings.feeds.sourcesUnit }} {{ strings.feeds.assigned }}
        </span>
      </div>

      <!-- Schedule -->
      <div class="flex items-center gap-2 text-sm">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
          <Calendar :size="16" class="text-purple-400" :stroke-width="2" />
        </div>
        <span class="text-text-secondary">{{ scheduleText }}</span>
      </div>

      <!-- Last Run -->
      <div class="flex items-center gap-2 text-sm">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-bg-hover">
          <component :is="lastRunConfig.icon" :size="16" :class="lastRunConfig.color" :stroke-width="2" />
        </div>
        <span class="text-text-secondary">{{ strings.feeds.status.lastRun }}: {{ lastRunConfig.text }}</span>
      </div>
    </div>

    <template #footer>
      <div class="grid grid-cols-[auto_1fr_auto] items-center gap-3">
        <!-- Toggle Switch -->
        <ToggleSwitch
          :model-value="feed.schedule_enabled"
          @update:model-value="handleToggle"
          :label="strings.feeds.actions.toggleFeedSchedule"
        />

        <!-- Run Now Button (centered) -->
        <button
          @click="emit('run', feed.id)"
          :disabled="isRunning"
          class="group/run flex items-center justify-center gap-1.5 rounded-lg bg-status-success/10 px-3 py-1.5 text-sm font-medium text-status-success transition-all hover:bg-status-success hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
          :title="strings.feeds.actions.runFeedNow"
        >
          <PlayCircle
            :size="16"
            :stroke-width="2"
            :class="isRunning ? 'animate-spin' : 'transition-transform group-hover/run:scale-110'"
          />
          {{ isRunning ? strings.feeds.running : strings.feeds.runNow }}
        </button>

        <!-- Export, Edit & Delete Buttons -->
        <div class="flex items-center gap-1">
          <button
            @click="emit('export', feed.id)"
            class="rounded-lg p-2 text-text-muted transition-all hover:bg-accent-primary/10 hover:text-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.feeds.actions.exportFeedBundle"
          >
            <Download :size="18" :stroke-width="2" />
          </button>

          <button
            @click="emit('edit', feed)"
            class="rounded-lg p-2 text-text-muted transition-all hover:bg-bg-hover hover:text-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.feeds.actions.editFeed"
          >
            <Edit :size="18" :stroke-width="2" />
          </button>

          <button
            @click="emit('delete', feed.id)"
            class="rounded-lg p-2 text-text-muted transition-all hover:bg-status-failed/10 hover:text-status-failed focus:outline-none focus:ring-2 focus:ring-status-failed focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.feeds.actions.deleteFeed"
          >
            <Trash2 :size="18" :stroke-width="2" />
          </button>
        </div>
      </div>
    </template>
  </BaseCard>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
