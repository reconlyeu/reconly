<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { X, Calendar, Tag, Coins, FileText, ChevronDown, ChevronUp, ExternalLink, Edit3, Check } from 'lucide-vue-next';
import { marked } from 'marked';
import type { Digest, Exporter } from '@/types/entities';
import { extractPreviewImage } from '@/utils/imageUtils';
import { AgentPlaceholder, ArticlePlaceholder, EmailPlaceholder, YoutubePlaceholder } from '@/components/common/placeholders';
import TagInput from '@/components/common/TagInput.vue';
import ExportDropdown from '@/components/common/ExportDropdown.vue';
import { digestsApi } from '@/services/api';
import { strings } from '@/i18n/en';

// Configure marked for safe rendering
// breaks: false so single \n doesn't become <br> (YouTube transcripts have many line breaks)
marked.setOptions({
  breaks: false,
  gfm: true,
});

/**
 * Normalize markdown text to handle common LLM output patterns.
 * Converts non-standard formatting to proper markdown before rendering.
 */
function normalizeMarkdown(text: string): string {
  if (!text) return text;

  // Convert indented lines (4+ spaces) to bullet points
  // LLMs often output lists as indented text which email clients render as bullets
  text = text.replace(/^[ \t]{4,}(\S.*)/gm, '- $1');

  // Convert Unicode bullets to standard markdown dash
  text = text.replace(/^[\u2022\u25e6\u25aa\u25b8\u25ba\u25cf\u25cb]\s+/gm, '- ');

  // Convert en-dash/em-dash used as bullets
  text = text.replace(/^[\u2013\u2014]\s+/gm, '- ');

  return text;
}

interface Props {
  isOpen: boolean;
  digest: Digest | null;
}

interface Emits {
  (e: 'close'): void;
  (e: 'export', digest: Digest, exporter: Exporter): void;
  (e: 'tags-updated', digest: Digest): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isContentExpanded = ref(false);
const isEditingTags = ref(false);
const editedTags = ref<string[]>([]);
const imageLoadError = ref(false);
const queryClient = useQueryClient();

// Update tags mutation
const updateTagsMutation = useMutation({
  mutationFn: ({ id, tags }: { id: number; tags: string[] }) =>
    digestsApi.updateTags(id, tags),
  onSuccess: (updatedDigest) => {
    // Invalidate queries to refresh data
    queryClient.invalidateQueries({ queryKey: ['digests'] });
    queryClient.invalidateQueries({ queryKey: ['tags'] });
    emit('tags-updated', updatedDigest);
    isEditingTags.value = false;
  },
});

// Reset edit state when modal closes or digest changes
watch(() => props.isOpen, (isOpen) => {
  if (!isOpen) {
    isEditingTags.value = false;
    editedTags.value = [];
    imageLoadError.value = false;
  }
});

watch(() => props.digest, (digest) => {
  if (digest) {
    editedTags.value = [...(digest.tags || [])];
    imageLoadError.value = false;
  }
}, { immediate: true });

// Handle image load error
const handleImageError = () => {
  imageLoadError.value = true;
};

// Start editing tags
const startEditingTags = () => {
  if (props.digest) {
    editedTags.value = [...(props.digest.tags || [])];
    isEditingTags.value = true;
  }
};

// Save edited tags
const saveEditedTags = () => {
  if (props.digest) {
    updateTagsMutation.mutate({
      id: props.digest.id,
      tags: editedTags.value,
    });
  }
};

// Cancel editing
const cancelEditingTags = () => {
  isEditingTags.value = false;
  if (props.digest) {
    editedTags.value = [...(props.digest.tags || [])];
  }
};

// Format the original publication date
const formattedPublishedDate = computed(() => {
  if (!props.digest?.published_at) return '';
  const date = new Date(props.digest.published_at);
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
});

// Format the digest creation date
const formattedCreatedDate = computed(() => {
  if (!props.digest) return '';
  const date = new Date(props.digest.created_at);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
});

// Total tokens used (input + output)
const tokenCount = computed(() => {
  if (!props.digest) return 0;
  return (props.digest.tokens_in || 0) + (props.digest.tokens_out || 0);
});

// Check if we have a real source URL to link to (not for consolidated, email, or agent digests)
const hasSourceUrl = computed(() => {
  if (!props.digest?.url) return false;
  if (props.digest.url.startsWith('consolidated://')) return false;
  if (props.digest.url.startsWith('agent://')) return false; // Agent digests have synthetic URLs
  if (props.digest.source_type === 'imap') return false; // Email digests don't have meaningful URLs
  return true;
});

// Check if this is an email/IMAP source
const isEmail = computed(() => {
  return props.digest?.source_type?.toLowerCase() === 'imap';
});

// Check if this is an agent research source
const isAgent = computed(() => {
  return props.digest?.source_type?.toLowerCase() === 'agent';
});

// Format source type nicely (e.g., "youtube" -> "YouTube")
const sourceLabel = computed(() => {
  if (!props.digest?.source_type) return 'Article';
  const type = props.digest.source_type;
  const labels = strings.digests.sourceTypes;
  return labels[type as keyof typeof labels] || type.charAt(0).toUpperCase() + type.slice(1);
});

// Render markdown content (with normalization for LLM output patterns)
const renderedSummary = computed(() => {
  if (!props.digest?.summary) return '';
  return marked(normalizeMarkdown(props.digest.summary));
});

const renderedContent = computed(() => {
  if (!props.digest?.content) return '';
  return marked(props.digest.content);
});

// Check if this is a YouTube source
const isYouTube = computed(() => {
  return props.digest?.source_type?.toLowerCase() === 'youtube';
});

// Extract YouTube video ID from URL
const extractYouTubeVideoId = (url: string): string | null => {
  if (!url) return null;
  // Match various YouTube URL formats
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
  // First check for explicit image_url (e.g., from email extraction)
  if (props.digest?.image_url) return props.digest.image_url;

  // For YouTube, construct thumbnail URL from video ID
  if (isYouTube.value && props.digest?.url) {
    const videoId = extractYouTubeVideoId(props.digest.url);
    if (videoId) {
      return `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    }
  }

  // Fall back to extracting from content
  if (!props.digest?.content) return null;
  const html = marked(props.digest.content) as string;
  return extractPreviewImage(html);
});

const handleExport = (exporter: Exporter) => {
  if (props.digest) {
    emit('export', props.digest, exporter);
  }
};

const handleClose = () => {
  emit('close');
};

const toggleContent = () => {
  isContentExpanded.value = !isContentExpanded.value;
};
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen && digest"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="handleClose"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/90 backdrop-blur-md" />

        <!-- Modal -->
        <div
          class="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-base shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orbs -->
          <div class="pointer-events-none absolute -right-40 -top-40 h-96 w-96 rounded-full bg-accent-primary/10 blur-3xl" />
          <div class="pointer-events-none absolute -left-40 -bottom-40 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />

          <!-- Sticky Header -->
          <div class="sticky top-0 z-10 border-b border-border-subtle bg-bg-elevated/95 backdrop-blur-sm p-6">
            <div class="flex items-start justify-between gap-4">
              <!-- Source + Feed Badges -->
              <div class="flex flex-wrap items-center gap-2">
                <div class="flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-400">
                  <FileText :size="12" :stroke-width="2" />
                  {{ sourceLabel }}
                </div>
                <div v-if="digest.provider" class="flex items-center gap-1.5 rounded-full bg-purple-500/10 px-3 py-1.5 text-xs font-medium text-purple-400">
                  {{ digest.provider }}
                </div>
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2">
                <a
                  v-if="hasSourceUrl"
                  :href="digest.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="rounded-lg p-2 text-blue-400 transition-all hover:bg-blue-400/10 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-bg-base"
                  :title="strings.digests.card.viewOriginal"
                >
                  <ExternalLink :size="18" :stroke-width="2" />
                </a>
                <ExportDropdown
                  icon-only
                  size="sm"
                  @select="handleExport"
                />
                <button
                  @click="handleClose"
                  class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                >
                  <X :size="20" />
                </button>
              </div>
            </div>
          </div>

          <!-- Content -->
          <article class="relative p-8 md:p-12">
            <!-- Preview image or placeholder thumbnail (absolute positioned) -->
            <div class="absolute right-8 top-8 w-[134px] aspect-video rounded-lg border border-border-subtle bg-bg-surface overflow-hidden shadow-lg md:right-12 md:top-12">
              <img
                v-if="previewImageUrl && !imageLoadError"
                :src="previewImageUrl"
                alt="Preview"
                class="w-full h-full object-cover"
                @error="handleImageError"
              />
              <YoutubePlaceholder v-else-if="isYouTube" />
              <EmailPlaceholder v-else-if="isEmail" />
              <AgentPlaceholder v-else-if="isAgent" />
              <ArticlePlaceholder v-else />
            </div>
            <!-- Title -->
            <h1 class="mb-6 pr-36 md:pr-40 text-2xl font-bold leading-tight text-text-primary md:text-3xl">
              {{ digest.title }}
            </h1>

            <!-- Metadata Bar -->
            <div class="mb-8 flex flex-wrap items-center gap-4 border-b border-border-subtle pb-6 text-sm text-text-muted">
              <!-- Digest Created Date -->
              <div class="flex items-center gap-2" title="Digest created">
                <Calendar :size="16" :stroke-width="2" />
                {{ formattedCreatedDate }}
              </div>

              <!-- Original Publication Date (for individual items) -->
              <div v-if="formattedPublishedDate && !digest.url?.startsWith('consolidated://')" class="flex items-center gap-2 text-text-secondary" title="Original publication date">
                <span class="text-text-muted">{{ strings.digests.modal.published }}</span>
                {{ formattedPublishedDate }}
              </div>

              <!-- Tokens -->
              <div class="flex items-center gap-2">
                <Coins :size="16" :stroke-width="2" />
                {{ tokenCount.toLocaleString() }} {{ strings.digests.modal.tokens }}
              </div>
            </div>

            <!-- Summary -->
            <div class="mb-8">
              <h2 class="mb-3 text-sm font-semibold uppercase tracking-wider text-text-muted">
                Summary
              </h2>
              <div class="prose prose-invert max-w-none text-lg leading-relaxed text-text-secondary" v-html="renderedSummary" />
            </div>

            <!-- Content -->
            <div v-if="digest.content" class="mb-8">
              <button
                @click="toggleContent"
                class="mb-4 flex w-full items-center justify-between rounded-lg bg-bg-surface p-3 text-left transition-colors hover:bg-bg-hover"
              >
                <h2 class="text-sm font-semibold uppercase tracking-wider text-text-muted">
                  Full Content
                </h2>
                <component
                  :is="isContentExpanded ? ChevronUp : ChevronDown"
                  :size="20"
                  class="text-text-muted"
                />
              </button>
              <Transition name="expand">
                <div
                  v-if="isContentExpanded"
                  class="content-container max-h-96 overflow-y-auto rounded-lg border border-border-subtle bg-bg-surface p-4"
                >
                  <div class="prose prose-invert max-w-none text-text-primary" v-html="renderedContent" />
                </div>
              </Transition>
            </div>

            <!-- Tags -->
            <div class="mb-8">
              <div class="mb-3 flex items-center justify-between">
                <h2 class="text-sm font-semibold uppercase tracking-wider text-text-muted">
                  Tags
                </h2>
                <div v-if="!isEditingTags" class="flex items-center gap-2">
                  <button
                    type="button"
                    class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text-secondary"
                    @click="startEditingTags"
                  >
                    <Edit3 :size="12" />
                    Edit
                  </button>
                </div>
                <div v-else class="flex items-center gap-2">
                  <button
                    type="button"
                    class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-green-400 transition-colors hover:bg-green-400/10"
                    :disabled="updateTagsMutation.isPending.value"
                    @click="saveEditedTags"
                  >
                    <Check :size="12" />
                    {{ updateTagsMutation.isPending.value ? 'Saving...' : 'Save' }}
                  </button>
                  <button
                    type="button"
                    class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text-secondary"
                    :disabled="updateTagsMutation.isPending.value"
                    @click="cancelEditingTags"
                  >
                    <X :size="12" />
                    Cancel
                  </button>
                </div>
              </div>

              <!-- Display mode -->
              <div v-if="!isEditingTags">
                <div v-if="digest.tags && digest.tags.length > 0" class="flex flex-wrap gap-2">
                  <span
                    v-for="tag in digest.tags"
                    :key="tag"
                    class="flex items-center gap-1.5 rounded-full bg-bg-hover px-3 py-1.5 text-sm text-text-secondary"
                  >
                    <Tag :size="12" :stroke-width="2" />
                    {{ tag }}
                  </span>
                </div>
                <p v-else class="text-sm text-text-muted">
                  No tags yet. Click Edit to add tags.
                </p>
              </div>

              <!-- Edit mode -->
              <div v-else>
                <TagInput
                  v-model="editedTags"
                  placeholder="Add tags..."
                  :disabled="updateTagsMutation.isPending.value"
                />
              </div>
            </div>

            <!-- Footer Spacer -->
            <div class="h-8" />
          </article>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.98) translateY(20px);
  opacity: 0;
}

/* Expand transitions */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* Content container scrollbar */
.content-container::-webkit-scrollbar {
  width: 6px;
}

.content-container::-webkit-scrollbar-track {
  background: var(--color-bg-hover);
  border-radius: 3px;
}

.content-container::-webkit-scrollbar-thumb {
  background: var(--color-border-default);
  border-radius: 3px;
}

.content-container::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}

/* Custom scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: var(--color-bg-surface);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: var(--color-bg-hover);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: var(--color-border-default);
}

/* Prose styling for content - use :deep() to penetrate v-html */
.prose {
  color: var(--color-text-primary);
}

.prose :deep(h1),
.prose :deep(h2),
.prose :deep(h3),
.prose :deep(h4) {
  color: var(--color-text-primary);
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.prose :deep(p) {
  margin-bottom: 1em;
  line-height: 1.75;
}

.prose :deep(ul),
.prose :deep(ol) {
  margin-bottom: 1em;
  padding-left: 1.5em;
  list-style-position: outside;
}

.prose :deep(ul) {
  list-style-type: disc;
}

.prose :deep(ol) {
  list-style-type: decimal;
}

.prose :deep(li) {
  margin-bottom: 0.5em;
  display: list-item;
}

.prose :deep(a) {
  color: var(--color-accent-primary);
  text-decoration: underline;
}

.prose :deep(a:hover) {
  color: var(--color-accent-primary-hover);
}

/* Image styling - constrain size and handle broken images gracefully */
.prose :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.5rem;
  margin: 1em 0;
}

/* Hide broken images (shields.io, badges, etc. that fail to load) */
.prose :deep(img[src*="shields.io"]),
.prose :deep(img[src*="badge"]),
.prose :deep(img[src*=".svg"]),
.prose :deep(img[src*="camo.githubusercontent"]) {
  display: none;
}
</style>
