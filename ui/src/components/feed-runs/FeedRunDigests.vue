<script setup lang="ts">
import { FileText, ExternalLink } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { Digest } from '@/types/entities';

defineProps<{
  digests: Digest[];
}>();

const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString();
};

const truncate = (text: string | null | undefined, length: number): string => {
  if (!text) return '';
  if (text.length <= length) return text;
  return text.substring(0, length) + '...';
};
</script>

<template>
  <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
    <div class="flex items-center gap-2 mb-4">
      <FileText :size="18" class="text-accent-primary" />
      <h3 class="font-medium text-text-primary">{{ strings.feedRuns.details.digests }}</h3>
      <span class="text-sm text-text-secondary">({{ digests.length }})</span>
    </div>

    <div v-if="digests.length === 0" class="text-sm text-text-secondary">
      {{ strings.feedRuns.details.noDigests }}
    </div>

    <div v-else class="space-y-2">
      <a
        v-for="digest in digests"
        :key="digest.id"
        :href="`/digests?view=${digest.id}`"
        class="block p-3 rounded-lg bg-bg-primary hover:bg-bg-hover transition-colors group"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <h4 class="font-medium text-text-primary group-hover:text-accent-primary truncate">
              {{ digest.title || 'Untitled' }}
            </h4>
            <p class="text-sm text-text-secondary mt-1 line-clamp-2">
              {{ truncate(digest.summary, 150) }}
            </p>
            <div class="flex items-center gap-3 mt-2 text-xs text-text-muted">
              <span v-if="digest.source_type" class="capitalize">{{ digest.source_type }}</span>
              <span v-if="digest.created_at">{{ formatDate(digest.created_at) }}</span>
              <span v-if="digest.provider">{{ digest.provider }}</span>
            </div>
          </div>
          <ExternalLink :size="14" class="text-text-muted flex-shrink-0 ml-2 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </a>
    </div>
  </div>
</template>
