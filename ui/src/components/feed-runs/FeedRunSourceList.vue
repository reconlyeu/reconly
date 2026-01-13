<script setup lang="ts">
import { CheckCircle, XCircle, Clock, Rss, Globe, Youtube, ExternalLink } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { FeedRunSourceStatus, SourceType } from '@/types/entities';

defineProps<{
  sources: FeedRunSourceStatus[];
}>();

const getSourceIcon = (type: SourceType) => {
  switch (type) {
    case 'rss': return Rss;
    case 'youtube': return Youtube;
    case 'website':
    case 'blog':
    default: return Globe;
  }
};

const getStatusIcon = (status: 'success' | 'failed' | 'pending') => {
  switch (status) {
    case 'success': return CheckCircle;
    case 'failed': return XCircle;
    case 'pending': return Clock;
  }
};

const getStatusClass = (status: 'success' | 'failed' | 'pending'): string => {
  switch (status) {
    case 'success': return 'text-status-success';
    case 'failed': return 'text-status-error';
    case 'pending': return 'text-text-secondary';
  }
};
</script>

<template>
  <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
    <h3 class="font-medium text-text-primary mb-4">{{ strings.feedRuns.details.sources }}</h3>

    <div v-if="sources.length === 0" class="text-sm text-text-secondary">
      No source information available
    </div>

    <div v-else class="space-y-2">
      <component
        :is="source.source_url ? 'a' : 'div'"
        v-for="source in sources"
        :key="source.source_id"
        :href="source.source_url || undefined"
        :target="source.source_url ? '_blank' : undefined"
        :rel="source.source_url ? 'noopener noreferrer' : undefined"
        :class="[
          'flex items-center justify-between p-3 rounded-lg bg-bg-primary',
          source.source_url ? 'hover:bg-bg-hover cursor-pointer group' : ''
        ]"
      >
        <div class="flex items-center gap-3">
          <component :is="getSourceIcon(source.source_type)" :size="16" class="text-text-secondary" />
          <div>
            <p :class="['font-medium text-text-primary', source.source_url ? 'group-hover:text-accent-primary' : '']">
              {{ source.source_name }}
            </p>
            <p class="text-xs text-text-secondary capitalize">{{ source.source_type }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <ExternalLink
            v-if="source.source_url"
            :size="14"
            class="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
          />
          <div class="flex items-center gap-2">
            <component
              :is="getStatusIcon(source.status)"
              :size="16"
              :class="getStatusClass(source.status)"
            />
            <span :class="['text-sm capitalize', getStatusClass(source.status)]">
              {{ source.status }}
            </span>
          </div>
        </div>
      </component>
    </div>
  </div>
</template>
