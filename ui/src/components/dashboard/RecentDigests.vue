<script setup lang="ts">
/**
 * RecentDigests - Shows recent digests with compact card design
 */
import { ref, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { FileText, Calendar, Tag, ChevronRight } from 'lucide-vue-next';
import { marked } from 'marked';
import { dashboardApi } from '@/services/api';
import { strings } from '@/i18n/en';
import { extractPreviewImage } from '@/utils/imageUtils';
import { ArticlePlaceholder, YoutubePlaceholder } from '@/components/common/placeholders';
import BaseCard from '@/components/common/BaseCard.vue';

// Props
interface Props {
  limit?: number;
}
const props = withDefaults(defineProps<Props>(), {
  limit: 6,
});

// Configure marked
marked.setOptions({ breaks: false, gfm: true });

const { data: digestsData, isLoading } = useQuery({
  queryKey: ['recent-digests'],
  queryFn: () => dashboardApi.getRecentDigestsFiltered('all', props.limit),
  refetchInterval: 30000,
});

// Extract digests array from response
const digests = computed(() => digestsData.value?.digests ?? []);

function formatDate(timestamp: string | null): string {
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
}

// Check if digest has a real source URL (not consolidated)
function hasSourceUrl(url: string | null): boolean {
  return Boolean(url && !url.startsWith('consolidated://'));
}

// Check if this is a YouTube source
function isYouTube(sourceType: string | null): boolean {
  return sourceType?.toLowerCase() === 'youtube';
}

// Extract YouTube video ID from URL
function extractYouTubeVideoId(url: string): string | null {
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
}

// Get preview image URL
function getPreviewImageUrl(digest: { image_url?: string | null; url: string; source_type?: string | null; content?: string | null }): string | null {
  if (digest.image_url) return digest.image_url;

  if (isYouTube(digest.source_type) && digest.url) {
    const videoId = extractYouTubeVideoId(digest.url);
    if (videoId) {
      return `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    }
  }

  if (!digest.content) return null;
  const html = marked(digest.content) as string;
  return extractPreviewImage(html);
}

// Track image load errors per digest
const imageErrors = ref<Set<number>>(new Set());

function handleImageError(digestId: number): void {
  imageErrors.value.add(digestId);
}
</script>

<template>
  <div class="space-y-3">
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 4"
        :key="i"
        class="h-24 animate-pulse rounded-xl bg-bg-elevated"
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

    <!-- Digests list -->
    <div v-else class="space-y-3">
      <a
        v-for="(digest, index) in digests"
        :key="digest.id"
        :href="`/digests?view=${digest.id}`"
        class="group block animate-slide-in-right-fast"
        :style="{ animationDelay: `${index * 50}ms` }"
      >
        <BaseCard glow-color="primary" clickable>
          <div class="flex gap-3">
            <!-- Thumbnail -->
            <div class="w-20 h-14 shrink-0 rounded-lg border border-border-subtle bg-bg-surface overflow-hidden">
              <img
                v-if="getPreviewImageUrl(digest) && !imageErrors.has(digest.id)"
                :src="getPreviewImageUrl(digest)!"
                alt=""
                class="w-full h-full object-cover"
                @error="handleImageError(digest.id)"
              />
              <YoutubePlaceholder v-else-if="isYouTube(digest.source_type)" class="w-full h-full" />
              <ArticlePlaceholder v-else class="w-full h-full" />
            </div>

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <!-- Title -->
              <h4 class="font-semibold text-text-primary group-hover:text-accent-primary transition-colors line-clamp-1 mb-1">
                {{ digest.title || 'Untitled' }}
              </h4>

              <!-- Meta row -->
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
                <!-- Source type badge -->
                <div class="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-blue-400">
                  <FileText class="h-3 w-3" />
                  {{ digest.source_type || 'article' }}
                </div>
                <!-- Date -->
                <div class="flex items-center gap-1">
                  <Calendar class="h-3 w-3" />
                  {{ formatDate(digest.created_at) }}
                </div>
                <!-- Tags -->
                <div v-if="digest.tags && digest.tags.length > 0" class="flex items-center gap-1">
                  <Tag class="h-3 w-3" />
                  <span>{{ digest.tags[0] }}</span>
                  <span v-if="digest.tags.length > 1">+{{ digest.tags.length - 1 }}</span>
                </div>
              </div>
            </div>

            <!-- Arrow -->
            <div class="flex items-center">
              <ChevronRight
                class="h-5 w-5 shrink-0 text-text-muted opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100"
              />
            </div>
          </div>
        </BaseCard>
      </a>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
