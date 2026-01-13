<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { FileText, Calendar, Tag, ExternalLink } from 'lucide-vue-next';
import { marked } from 'marked';
import { dashboardApi } from '@/services/api';
import { strings } from '@/i18n/en';

// Configure marked
marked.setOptions({ breaks: false, gfm: true });

const { data: digests, isLoading } = useQuery({
  queryKey: ['recent-digests'],
  queryFn: () => dashboardApi.getRecentDigests(4),
  refetchInterval: 30000,
});

const formatDate = (timestamp: string | null) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
};

const getSourceIcon = (sourceType: string | null) => {
  // Return appropriate icon based on source type
  return FileText;
};

// Check if digest has a real source URL (not consolidated)
const hasSourceUrl = (url: string | null) => {
  return url && !url.startsWith('consolidated://');
};

// Render markdown for preview with formatting
const getRenderedSummary = (summary: string | null) => {
  if (!summary) return '<span class="text-text-muted">No summary available</span>';
  return marked(summary) as string;
};
</script>

<template>
  <div class="space-y-3">
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-32 animate-pulse rounded-xl bg-bg-elevated"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!digests || digests.length === 0"
      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-surface/50 py-12"
    >
      <FileText class="mb-3 h-12 w-12 text-text-muted opacity-50" />
      <p class="text-sm text-text-muted">{{ strings.dashboard.noDigests }}</p>
    </div>

    <!-- Digests grid -->
    <div v-else class="grid gap-3">
      <a
        v-for="(digest, index) in digests"
        :key="digest.id"
        :href="`/digests?view=${digest.id}`"
        class="group animate-slide-in-right-slow relative overflow-hidden rounded-xl border border-border-subtle bg-gradient-to-br from-bg-elevated/60 to-bg-surface/40 p-5 transition-all duration-300 hover:border-accent-primary/50 hover:shadow-xl hover:shadow-accent-primary/5"
        :style="{ animationDelay: `${index * 200}ms` }"
      >
        <!-- Hover gradient overlay -->
        <div
          class="pointer-events-none absolute inset-0 bg-gradient-to-br from-accent-primary/5 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        />

        <div class="relative z-10">
          <!-- Header: Icon, source type, and timestamp -->
          <div class="mb-3 flex items-start justify-between">
            <div class="flex items-center gap-2">
              <div
                class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-primary/10"
              >
                <component
                  :is="getSourceIcon(digest.source_type)"
                  class="h-5 w-5 text-accent-primary"
                />
              </div>
              <div>
                <div class="text-xs font-medium uppercase tracking-wide text-text-muted">
                  {{ digest.source_type || 'Article' }}
                </div>
                <div class="flex items-center gap-1.5 text-xs text-text-muted">
                  <Calendar class="h-3 w-3" />
                  {{ formatDate(digest.created_at) }}
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a
                v-if="hasSourceUrl(digest.url)"
                :href="digest.url"
                target="_blank"
                rel="noopener noreferrer"
                @click.stop
                class="rounded-lg p-1.5 text-blue-400 opacity-0 transition-all hover:bg-blue-400/10 group-hover:opacity-100"
                title="View original"
              >
                <ExternalLink class="h-4 w-4" />
              </a>
              <div
                v-if="digest.provider"
                class="rounded-full bg-purple-500/10 px-2 py-0.5 text-xs font-medium text-purple-400"
              >
                {{ digest.provider }}
              </div>
            </div>
          </div>

          <!-- Title -->
          <h3
            class="mb-2 line-clamp-2 font-semibold leading-snug text-text-primary transition-colors duration-300 group-hover:text-accent-primary"
          >
            {{ digest.title || 'Untitled' }}
          </h3>

          <!-- Summary preview -->
          <div
            class="mb-3 line-clamp-2 text-sm leading-relaxed text-text-secondary prose-preview"
            v-html="getRenderedSummary(digest.summary)"
          />

          <!-- Footer: Tags -->
          <div v-if="digest.tags && digest.tags.length > 0" class="flex items-center gap-1.5">
            <Tag class="h-3.5 w-3.5 text-text-muted" />
            <div class="flex gap-1.5">
              <span
                v-for="tag in digest.tags.slice(0, 2)"
                :key="tag"
                class="rounded-md bg-bg-surface px-2 py-0.5 text-xs font-medium text-text-muted"
              >
                {{ tag }}
              </span>
              <span
                v-if="digest.tags.length > 2"
                class="rounded-md bg-bg-surface px-2 py-0.5 text-xs font-medium text-text-muted"
              >
                +{{ digest.tags.length - 2 }}
              </span>
            </div>
          </div>
        </div>

        <!-- Accent line that grows on hover -->
        <div
          class="absolute bottom-0 left-0 h-0.5 w-0 bg-gradient-to-r from-accent-primary to-accent-primary-hover transition-all duration-500 group-hover:w-full"
        />
      </a>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Prose preview styling for markdown content */
.prose-preview :deep(p) {
  margin: 0;
  display: inline;
}

.prose-preview :deep(strong) {
  font-weight: 600;
  color: var(--color-text-primary);
}

.prose-preview :deep(em) {
  font-style: italic;
}

.prose-preview :deep(ul),
.prose-preview :deep(ol) {
  display: inline;
  padding: 0;
  margin: 0;
}

.prose-preview :deep(li) {
  display: inline;
}

.prose-preview :deep(li)::before {
  content: ' • ';
}

.prose-preview :deep(code) {
  background: var(--color-bg-hover);
  padding: 0.1em 0.3em;
  border-radius: 0.25rem;
  font-size: 0.9em;
}
</style>
