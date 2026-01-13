<script setup lang="ts">
/**
 * NodeDetailSidebar - Shows details for the selected graph node
 *
 * Displays:
 * - Node type icon and label
 * - Digest details (title, summary, published date, source, tags)
 * - Tag details (count of digests)
 * - Source details (type, URL)
 * - Actions (view digest, expand connections)
 */

import { computed } from 'vue';
import { strings } from '@/i18n/en';
import type { GraphNode } from '@/types/entities';
import BaseCard from '@/components/common/BaseCard.vue';
import {
  FileText,
  Tag,
  Rss,
  ListTree,
  Calendar,
  ExternalLink,
  Expand,
  X,
} from 'lucide-vue-next';

interface Props {
  node: GraphNode | null;
  isOpen: boolean;
}

interface Emits {
  (e: 'close'): void;
  (e: 'expand-node', node: GraphNode): void;
  (e: 'view-digest', digestId: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// Node type icons
const nodeIcons = {
  digest: FileText,
  tag: Tag,
  source: Rss,
  feed: ListTree,
};

// Node type colors
const nodeColors = {
  digest: 'text-blue-400 bg-blue-400/10',
  tag: 'text-purple-400 bg-purple-400/10',
  source: 'text-green-400 bg-green-400/10',
  feed: 'text-amber-400 bg-amber-400/10',
};

const nodeIcon = computed(() => {
  if (!props.node) return FileText;
  return nodeIcons[props.node.type] || FileText;
});

const nodeColorClass = computed(() => {
  if (!props.node) return nodeColors.digest;
  return nodeColors[props.node.type] || nodeColors.digest;
});

const isDigest = computed(() => props.node?.type === 'digest');
const isTag = computed(() => props.node?.type === 'tag');
const isSource = computed(() => props.node?.type === 'source');

// Extract digest ID from node ID (format: "d_42")
const digestId = computed(() => {
  if (!props.node || !isDigest.value) return null;
  const match = props.node.id.match(/^d_(\d+)$/);
  return match ? parseInt(match[1], 10) : null;
});

// Format date
const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
};

const handleViewDigest = () => {
  if (digestId.value) {
    emit('view-digest', digestId.value);
  }
};

const handleExpandNode = () => {
  if (props.node) {
    emit('expand-node', props.node);
  }
};
</script>

<template>
  <transition
    enter-active-class="transition-transform duration-300 ease-out"
    leave-active-class="transition-transform duration-200 ease-in"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="isOpen"
      class="fixed right-0 top-16 bottom-0 w-80 bg-bg-surface border-l border-border-subtle shadow-xl z-40 overflow-y-auto"
    >
      <!-- Header -->
      <div class="sticky top-0 bg-bg-surface border-b border-border-subtle p-4 flex items-center justify-between">
        <h3 class="text-lg font-semibold text-text-primary">
          {{ strings.knowledgeGraph.sidebar.details }}
        </h3>
        <button
          @click="emit('close')"
          class="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Content -->
      <div class="p-4 space-y-4">
        <!-- No Selection -->
        <div v-if="!node" class="text-center text-text-secondary py-8">
          <FileText class="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>{{ strings.knowledgeGraph.sidebar.noSelection }}</p>
        </div>

        <!-- Node Details -->
        <template v-else>
          <!-- Node Type Badge -->
          <div class="flex items-center gap-3">
            <div
              class="w-10 h-10 rounded-lg flex items-center justify-center"
              :class="nodeColorClass"
            >
              <component :is="nodeIcon" class="w-5 h-5" />
            </div>
            <div>
              <span class="text-xs font-medium text-text-muted uppercase tracking-wider">
                {{ strings.knowledgeGraph.nodeTypes[node.type] }}
              </span>
              <h4 class="text-base font-semibold text-text-primary line-clamp-2">
                {{ node.label }}
              </h4>
            </div>
          </div>

          <!-- Digest Details -->
          <template v-if="isDigest">
            <!-- Summary -->
            <div v-if="node.data.summary" class="space-y-1">
              <p class="text-sm text-text-secondary line-clamp-4">
                {{ node.data.summary }}
              </p>
            </div>

            <!-- Metadata -->
            <div class="space-y-3">
              <!-- Published Date -->
              <div v-if="node.data.published_at" class="flex items-center gap-2 text-sm">
                <Calendar class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">{{ strings.knowledgeGraph.sidebar.published }}:</span>
                <span class="text-text-primary">{{ formatDate(node.data.published_at) }}</span>
              </div>

              <!-- Source -->
              <div v-if="node.data.source_name" class="flex items-center gap-2 text-sm">
                <Rss class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">{{ strings.knowledgeGraph.sidebar.source }}:</span>
                <span class="text-text-primary">{{ node.data.source_name }}</span>
              </div>

              <!-- Feed -->
              <div v-if="node.data.feed_title" class="flex items-center gap-2 text-sm">
                <ListTree class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">{{ strings.knowledgeGraph.sidebar.feed }}:</span>
                <span class="text-text-primary">{{ node.data.feed_title }}</span>
              </div>

              <!-- Tags -->
              <div v-if="node.data.tags?.length" class="space-y-2">
                <div class="flex items-center gap-2 text-sm">
                  <Tag class="w-4 h-4 text-text-muted" />
                  <span class="text-text-secondary">{{ strings.knowledgeGraph.sidebar.tags }}:</span>
                </div>
                <div class="flex flex-wrap gap-1.5 pl-6">
                  <span
                    v-for="tag in node.data.tags"
                    :key="tag"
                    class="px-2 py-0.5 rounded-full bg-purple-400/10 text-purple-400 text-xs font-medium"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex flex-col gap-2 pt-2">
              <button
                @click="handleViewDigest"
                class="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg bg-accent-primary text-white text-sm font-medium hover:bg-accent-primary/90 transition-colors"
              >
                <ExternalLink class="w-4 h-4" />
                {{ strings.knowledgeGraph.sidebar.viewDigest }}
              </button>
              <button
                @click="handleExpandNode"
                class="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg border border-border-subtle text-text-secondary text-sm font-medium hover:bg-bg-hover hover:text-text-primary transition-colors"
              >
                <Expand class="w-4 h-4" />
                {{ strings.knowledgeGraph.sidebar.expandNode }}
              </button>
            </div>
          </template>

          <!-- Tag Details -->
          <template v-else-if="isTag">
            <div class="space-y-3">
              <div class="flex items-center gap-2 text-sm">
                <FileText class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">Digests:</span>
                <span class="text-text-primary font-medium">{{ node.data.count || 0 }}</span>
              </div>
            </div>

            <button
              @click="handleExpandNode"
              class="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg border border-border-subtle text-text-secondary text-sm font-medium hover:bg-bg-hover hover:text-text-primary transition-colors"
            >
              <Expand class="w-4 h-4" />
              {{ strings.knowledgeGraph.sidebar.expandNode }}
            </button>
          </template>

          <!-- Source Details -->
          <template v-else-if="isSource">
            <div class="space-y-3">
              <div v-if="node.data.source_type" class="flex items-center gap-2 text-sm">
                <Rss class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">Type:</span>
                <span class="text-text-primary capitalize">{{ node.data.source_type }}</span>
              </div>
            </div>

            <button
              @click="handleExpandNode"
              class="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg border border-border-subtle text-text-secondary text-sm font-medium hover:bg-bg-hover hover:text-text-primary transition-colors"
            >
              <Expand class="w-4 h-4" />
              {{ strings.knowledgeGraph.sidebar.expandNode }}
            </button>
          </template>

          <!-- Feed Details -->
          <template v-else>
            <div class="space-y-3">
              <div v-if="node.data.digest_count" class="flex items-center gap-2 text-sm">
                <FileText class="w-4 h-4 text-text-muted" />
                <span class="text-text-secondary">Digests:</span>
                <span class="text-text-primary font-medium">{{ node.data.digest_count }}</span>
              </div>
            </div>

            <button
              @click="handleExpandNode"
              class="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg border border-border-subtle text-text-secondary text-sm font-medium hover:bg-bg-hover hover:text-text-primary transition-colors"
            >
              <Expand class="w-4 h-4" />
              {{ strings.knowledgeGraph.sidebar.expandNode }}
            </button>
          </template>
        </template>
      </div>
    </div>
  </transition>
</template>
