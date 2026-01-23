<script setup lang="ts">
/**
 * Card for displaying a fetcher option.
 * Shows activation status badge, extension indicator, and toggle switch.
 * Used in FetcherSettings for listing and selecting fetchers.
 */
import { computed } from 'vue';
import {
  ArrowRightToLine,
  Check,
  X,
  AlertCircle,
  Settings,
  Puzzle,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { Fetcher } from '@/types/entities';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';

interface Props {
  fetcher: Fetcher;
  selected?: boolean;
  isToggling?: boolean;
}

interface Emits {
  (e: 'select', fetcherName: string): void;
  (e: 'toggle', fetcherName: string, enabled: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  isToggling: false,
});

const emit = defineEmits<Emits>();

const handleClick = () => {
  emit('select', props.fetcher.name);
};

const handleToggle = (enabled: boolean) => {
  emit('toggle', props.fetcher.name, enabled);
};

// Status configuration following ExporterCard pattern
type StatusType = 'active' | 'needs_config' | 'disabled';

const status = computed<StatusType>(() => {
  const { enabled, is_configured } = props.fetcher;
  if (enabled && is_configured) return 'active';
  if (!is_configured) return 'needs_config';
  return 'disabled';
});

const statusConfig = computed(() => {
  const configs = {
    active: {
      label: strings.settings.fetchers.status.active,
      color: 'bg-green-500/10 text-green-400 border-green-500/20',
      icon: Check,
      dotColor: 'bg-green-500',
    },
    needs_config: {
      label: strings.settings.fetchers.status.needsConfig,
      color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      icon: AlertCircle,
      dotColor: 'bg-amber-500',
    },
    disabled: {
      label: strings.settings.fetchers.status.disabled,
      color: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
      icon: X,
      dotColor: 'bg-gray-500',
    },
  };
  return configs[status.value];
});

// Get friendly name for fetcher (capitalize first letter)
const displayName = computed(() => {
  const name = props.fetcher.name;
  return name.charAt(0).toUpperCase() + name.slice(1);
});

// Tooltip for disabled toggle
const toggleTooltip = computed(() => {
  if (!props.fetcher.can_enable && !props.fetcher.enabled) {
    return strings.settings.fetchers.configureRequired;
  }
  return props.fetcher.enabled ? strings.settings.fetchers.disableFetcher : strings.settings.fetchers.enableFetcher;
});

// Has configurable fields
const hasConfig = computed(() => {
  return props.fetcher.config_schema && props.fetcher.config_schema.fields.length > 0;
});
</script>

<template>
  <button
    type="button"
    @click="handleClick"
    class="group relative overflow-hidden rounded-2xl border bg-gradient-to-br from-bg-elevated to-bg-surface p-5 text-left transition-all duration-300"
    :class="[
      selected
        ? 'border-accent-primary ring-2 ring-accent-primary/20 shadow-lg shadow-accent-primary/10'
        : 'border-border-subtle hover:border-border-default hover:shadow-xl hover:shadow-black/5'
    ]"
  >
    <!-- Hover glow effect -->
    <div
      class="absolute inset-0 bg-gradient-to-br from-accent-primary/[0.02] to-transparent opacity-0 transition-opacity duration-500"
      :class="{ 'opacity-100': selected, 'group-hover:opacity-100': !selected }"
    />

    <!-- Decorative corner orb -->
    <div
      class="absolute -right-12 -top-12 h-32 w-32 rounded-full bg-purple-400 opacity-0 blur-3xl transition-all duration-700"
      :class="[selected ? 'opacity-30' : 'group-hover:opacity-20']"
    />

    <!-- Status badge (top-right) -->
    <div
      class="absolute right-3 top-3 flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
      :class="statusConfig.color"
    >
      <div
        class="h-2 w-2 rounded-full animate-pulse"
        :class="statusConfig.dotColor"
      />
      {{ statusConfig.label }}
    </div>

    <div class="relative flex flex-col gap-3">
      <!-- Icon and name -->
      <div class="flex items-center gap-3">
        <div
          class="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500/10 transition-all duration-300 group-hover:scale-110"
        >
          <ArrowRightToLine
            :size="22"
            :stroke-width="2"
            class="text-purple-400"
          />
        </div>
        <div>
          <div class="text-base font-semibold text-text-primary transition-colors group-hover:text-accent-primary">
            {{ displayName }}
          </div>
          <div class="text-xs text-text-muted">{{ strings.settings.fetchers.fetcher }}</div>
        </div>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-muted line-clamp-2">
        {{ fetcher.description }}
      </p>

      <!-- Toggle and feature badges -->
      <div class="flex items-center gap-3 pt-1">
        <!-- Toggle switch (left) -->
        <div
          @click.stop
          :title="toggleTooltip"
        >
          <ToggleSwitch
            :model-value="fetcher.enabled"
            @update:model-value="handleToggle"
            :disabled="(!fetcher.can_enable && !fetcher.enabled) || isToggling"
            size="sm"
          />
        </div>

        <!-- Feature badges -->
        <div class="flex flex-wrap gap-2">
          <span
            v-if="fetcher.is_extension"
            class="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-400"
          >
            <Puzzle :size="12" />
            {{ strings.settings.fetchers.extension }}
          </span>
          <span
            v-if="hasConfig"
            class="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-400"
          >
            <Settings :size="12" />
            {{ strings.settings.exports.features.configurable }}
          </span>
        </div>
      </div>
    </div>
  </button>
</template>
