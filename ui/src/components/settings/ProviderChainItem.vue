<script setup lang="ts">
/**
 * Individual provider item in the fallback chain.
 *
 * Low-height row with drag handle, position, provider info, status, and action buttons.
 * Emits events for selection, removal, and drag operations.
 */
import { computed } from 'vue';
import { GripVertical, Settings, X, Cloud, Server } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { Provider, ProviderStatus } from '@/types/entities';

interface Props {
  provider: Provider;
  position: number;
  configuredModel?: string | null;
  isSelected: boolean;
  isDragging?: boolean;
  isDragOver?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  configuredModel: null,
  isDragging: false,
  isDragOver: false,
});

const emit = defineEmits<{
  select: [provider: Provider];
  remove: [provider: Provider];
  dragstart: [event: DragEvent, provider: Provider];
  dragend: [event: DragEvent];
  dragover: [event: DragEvent];
  drop: [event: DragEvent];
}>();

// Status configuration for visual display
const statusConfig = computed(() => {
  const configs: Record<ProviderStatus, { label: string; dotClass: string }> = {
    available: {
      label: strings.settings.providers.status.available,
      dotClass: 'bg-status-success',
    },
    configured: {
      label: strings.settings.providers.status.configured,
      dotClass: 'bg-blue-500',
    },
    not_configured: {
      label: strings.settings.providers.status.notConfigured,
      dotClass: 'bg-status-failed',
    },
    unavailable: {
      label: strings.settings.providers.status.unavailable,
      dotClass: 'bg-amber-500',
    },
  };
  return configs[props.provider.status] || configs.unavailable;
});

// Get display name for provider - use metadata if available, fallback to name capitalization
const displayName = computed(() => {
  return props.provider.metadata?.display_name ||
    props.provider.name.charAt(0).toUpperCase() + props.provider.name.slice(1);
});

// Get current model - prefer configured model, then provider default
const currentModel = computed(() => {
  // If a model is configured in settings, use that
  if (props.configuredModel) {
    return props.configuredModel;
  }
  // Otherwise use the provider's default model
  if (!props.provider.models || props.provider.models.length === 0) {
    return null;
  }
  const defaultModel = props.provider.models.find(m => m.is_default);
  return defaultModel?.name || props.provider.models[0]?.name || null;
});

// Type label (Local or Cloud)
const typeLabel = computed(() => {
  return props.provider.is_local ? strings.settings.providers.local : strings.settings.providers.cloud;
});

// Handle drag start
const handleDragStart = (event: DragEvent) => {
  event.dataTransfer?.setData('text/plain', props.provider.name);
  event.dataTransfer!.effectAllowed = 'move';
  emit('dragstart', event, props.provider);
};

// Handle drag end
const handleDragEnd = (event: DragEvent) => {
  emit('dragend', event);
};

// Handle drag over
const handleDragOver = (event: DragEvent) => {
  event.preventDefault();
  event.dataTransfer!.dropEffect = 'move';
  emit('dragover', event);
};

// Handle drop
const handleDrop = (event: DragEvent) => {
  event.preventDefault();
  emit('drop', event);
};
</script>

<template>
  <div
    :class="[
      'flex items-center gap-3 rounded-lg border px-4 py-3 transition-all',
      isSelected
        ? 'border-accent-primary bg-accent-primary/5'
        : 'border-border-subtle bg-bg-surface hover:border-border-default',
      isDragging && 'opacity-50',
      isDragOver && 'border-accent-primary border-dashed',
    ]"
    draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @dragover="handleDragOver"
    @drop="handleDrop"
  >
    <!-- Drag Handle -->
    <div class="cursor-grab active:cursor-grabbing text-text-muted hover:text-text-secondary">
      <GripVertical :size="18" />
    </div>

    <!-- Position Number -->
    <span class="w-6 text-center text-sm font-medium text-text-muted">
      {{ position }}.
    </span>

    <!-- Provider Info -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="font-medium text-text-primary truncate">{{ displayName }}</span>
        <span class="flex items-center gap-1 text-xs text-text-muted">
          <component :is="provider.is_local ? Server : Cloud" :size="12" />
          {{ typeLabel }}
        </span>
      </div>
      <div v-if="currentModel" class="text-xs text-text-muted truncate">
        {{ currentModel }}
      </div>
    </div>

    <!-- Status Badge -->
    <div class="flex items-center gap-1.5 text-xs text-text-secondary">
      <div
        class="h-2 w-2 rounded-full"
        :class="statusConfig.dotClass"
      />
      <span class="hidden sm:inline">{{ statusConfig.label }}</span>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-1">
      <button
        type="button"
        @click.stop="emit('select', provider)"
        :class="[
          'flex h-8 w-8 items-center justify-center rounded-lg transition-colors',
          isSelected
            ? 'bg-accent-primary text-white'
            : 'text-text-muted hover:bg-bg-hover hover:text-text-primary',
        ]"
        :title="strings.settings.providers.configureProvider"
      >
        <Settings :size="16" />
      </button>
      <button
        type="button"
        @click.stop="emit('remove', provider)"
        class="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:bg-status-failed/10 hover:text-status-failed transition-colors"
        :title="strings.settings.providers.removeFromChain"
      >
        <X :size="16" />
      </button>
    </div>
  </div>
</template>
