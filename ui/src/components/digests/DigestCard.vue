<script setup lang="ts">
import { computed, ref } from 'vue';
import { FileText, Calendar, Tag, Coins, Trash2, ExternalLink } from 'lucide-vue-next';
import { useConfirm } from '@/composables/useConfirm';
import { marked } from 'marked';
import type { Digest, Exporter } from '@/types/entities';
import { features } from '@/config/features';
import { extractPreviewImage } from '@/utils/imageUtils';
import BaseCard from '@/components/common/BaseCard.vue';
import ExportDropdown from '@/components/common/ExportDropdown.vue';
import { AgentPlaceholder, ArticlePlaceholder, EmailPlaceholder, YoutubePlaceholder } from '@/components/common/placeholders';

// Configure marked
marked.setOptions({ breaks: false, gfm: true });

interface Props {
  digest: Digest;
}

interface Emits {
  (e: 'view', digest: Digest): void;
  (e: 'export', digest: Digest, exporter: Exporter): void;
  (e: 'delete', digestId: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// Show created_at (when the digest was created)
const formattedDate = computed(() => {
  const date = new Date(props.digest.created_at);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
});

// Check if this is a consolidated digest (synthetic URL)
const isConsolidated = computed(() => {
  return props.digest.url?.startsWith('consolidated://') || props.digest.consolidated_count > 1;
});

// Check if we have a real source URL to link to (not for consolidated, email, or agent digests)
const hasSourceUrl = computed(() => {
  if (!props.digest.url) return false;
  if (props.digest.url.startsWith('consolidated://')) return false;
  if (props.digest.url.startsWith('agent://')) return false; // Agent digests have synthetic URLs
  if (props.digest.source_type === 'imap') return false; // Email digests don't have meaningful URLs
  return true;
});

// Check if this is an email/IMAP source
const isEmail = computed(() => {
  return props.digest.source_type?.toLowerCase() === 'imap';
});

// Check if this is an agent research source
const isAgent = computed(() => {
  return props.digest.source_type?.toLowerCase() === 'agent';
});

const estimatedCost = computed(() => {
  return props.digest.estimated_cost || 0;
});

// Render markdown for preview with formatting
const renderedSummary = computed(() => {
  if (!props.digest.summary) return '';
  return marked(props.digest.summary) as string;
});

// Check if this is a YouTube source
const isYouTube = computed(() => {
  return props.digest.source_type?.toLowerCase() === 'youtube';
});

// Extract YouTube video ID from URL
const extractYouTubeVideoId = (url: string): string | null => {
  if (!url) return null;
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/,
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
};

// Get preview image: prefer explicit image_url, then YouTube thumbnail, fall back to extracting from content
const previewImageUrl = computed(() => {
  if (props.digest.image_url) return props.digest.image_url;

  // For YouTube, construct thumbnail URL from video ID
  if (isYouTube.value && props.digest.url) {
    const videoId = extractYouTubeVideoId(props.digest.url);
    if (videoId) {
      return `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    }
  }

  // Fall back to extracting from content
  if (!props.digest.content) return null;
  const html = marked(props.digest.content) as string;
  return extractPreviewImage(html);
});

const handleExport = (exporter: Exporter) => {
  emit('export', props.digest, exporter);
};

const handleDelete = (e: Event) => {
  e.stopPropagation();
  const { confirmDelete } = useConfirm();
  if (confirmDelete(props.digest.title || 'this digest', 'digest')) {
    emit('delete', props.digest.id);
  }
};

const handleClick = () => {
  emit('view', props.digest);
};

// Handle image load error - show placeholder instead
const imageLoadError = ref(false);
const handleImageError = () => {
  imageLoadError.value = true;
};
</script>

<template>
  <BaseCard clickable glow-color="primary" @click="handleClick">
    <template #header>
      <!-- Source Type + Provider Badges -->
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
          <FileText :size="12" :stroke-width="2" />
          {{ digest.source_type || 'article' }}
        </div>
        <div v-if="digest.provider" class="flex items-center gap-1.5 rounded-full bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-400">
          {{ digest.provider }}
        </div>
      </div>
    </template>

    <!-- Preview image or placeholder (absolute positioned top-right) -->
    <div class="absolute right-0 top-0 w-[115px] aspect-video rounded border border-border-subtle bg-bg-surface overflow-hidden">
      <img
        v-if="previewImageUrl && !imageLoadError"
        :src="previewImageUrl"
        alt=""
        class="w-full h-full object-cover"
        @error="handleImageError"
      />
      <YoutubePlaceholder v-else-if="isYouTube" />
      <EmailPlaceholder v-else-if="isEmail" />
      <AgentPlaceholder v-else-if="isAgent" />
      <ArticlePlaceholder v-else />
    </div>

    <!-- Title -->
    <h3
      class="mb-3 pr-32 text-xl font-bold leading-tight text-text-primary transition-colors duration-300 group-hover:text-accent-primary line-clamp-2"
    >
      {{ digest.title }}
    </h3>

    <!-- Summary Preview -->
    <div
      class="mb-4 text-sm leading-relaxed text-text-secondary line-clamp-3 prose-preview"
      v-html="renderedSummary"
    />

    <!-- Tags -->
    <div v-if="digest.tags && digest.tags.length > 0" class="flex flex-wrap gap-2">
      <span
        v-for="tag in digest.tags.slice(0, 3)"
        :key="tag"
        class="flex items-center gap-1 rounded-full bg-bg-hover px-2.5 py-1 text-xs text-text-muted"
      >
        <Tag :size="10" :stroke-width="2" />
        {{ tag }}
      </span>
      <span v-if="digest.tags.length > 3" class="flex items-center rounded-full bg-bg-hover px-2.5 py-1 text-xs text-text-muted">
        +{{ digest.tags.length - 3 }}
      </span>
    </div>

    <template #footer>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4 text-xs text-text-muted">
          <!-- Date -->
          <div class="flex items-center gap-1.5">
            <Calendar :size="14" :stroke-width="2" />
            {{ formattedDate }}
          </div>

          <!-- Cost (Enterprise only) -->
          <div v-if="features.costDisplay && estimatedCost > 0" class="flex items-center gap-1.5">
            <Coins :size="14" :stroke-width="2" />
            ${{ estimatedCost.toFixed(4) }}
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-1">
          <a
            v-if="hasSourceUrl"
            :href="digest.url"
            target="_blank"
            rel="noopener noreferrer"
            @click.stop
            class="rounded-lg p-2 text-blue-400 opacity-0 transition-all hover:bg-blue-400/10 group-hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-bg-base"
            title="View original"
          >
            <ExternalLink :size="16" :stroke-width="2" />
          </a>
          <div class="opacity-0 transition-all group-hover:opacity-100 focus-within:opacity-100">
            <ExportDropdown
              icon-only
              size="sm"
              button-class="rounded-lg p-2 text-amber-400 transition-all hover:bg-amber-400/10 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 focus:ring-offset-bg-base"
              @select="handleExport"
            />
          </div>
          <button
            @click="handleDelete"
            class="rounded-lg p-2 text-text-muted opacity-0 transition-all hover:bg-status-failed/10 hover:text-status-failed group-hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-status-failed focus:ring-offset-2 focus:ring-offset-bg-base"
            title="Delete digest"
          >
            <Trash2 :size="16" :stroke-width="2" />
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

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
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
