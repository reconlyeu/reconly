<script setup lang="ts">
/**
 * Selectable card for displaying an exporter option.
 * Used in ExporterSelector for choosing default export format.
 * Shows activation status badge and toggle switch.
 */
import { computed } from 'vue';
import {
  FileJson,
  FileSpreadsheet,
  FileText,
  FileType,
  Check,
  X,
  AlertCircle,
  HardDrive,
  Settings,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { Exporter } from '@/types/entities';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';

interface Props {
  exporter: Exporter;
  selected?: boolean;
  isToggling?: boolean;
}

interface Emits {
  (e: 'select', exporterName: string): void;
  (e: 'toggle', exporterName: string, enabled: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  isToggling: false,
});

const emit = defineEmits<Emits>();

const handleClick = () => {
  emit('select', props.exporter.name);
};

const handleToggle = (enabled: boolean) => {
  emit('toggle', props.exporter.name, enabled);
};

// Status configuration following ProviderChainItem pattern
type StatusType = 'active' | 'misconfigured' | 'disabled' | 'not_configured';

const status = computed<StatusType>(() => {
  const { enabled, is_configured } = props.exporter;
  if (enabled && is_configured) return 'active';
  if (enabled && !is_configured) return 'misconfigured';
  if (!enabled && is_configured) return 'disabled';
  return 'not_configured';
});

const statusConfig = computed(() => {
  const configs = {
    active: {
      label: strings.settings.exports.status.active,
      color: 'bg-green-500/10 text-green-400 border-green-500/20',
      icon: Check,
      dotColor: 'bg-green-500',
    },
    misconfigured: {
      label: strings.settings.exports.status.misconfigured,
      color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      icon: AlertCircle,
      dotColor: 'bg-amber-500',
    },
    disabled: {
      label: strings.settings.exports.status.disabled,
      color: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
      icon: X,
      dotColor: 'bg-gray-500',
    },
    not_configured: {
      label: strings.settings.exports.status.notConfigured,
      color: 'bg-red-500/10 text-red-400 border-red-500/20',
      icon: X,
      dotColor: 'bg-red-500',
    },
  };
  return configs[status.value];
});

// Get icon based on exporter name/type (keep icon mapping - lucide icons can't be dynamically loaded)
const ExporterIcon = computed(() => {
  const iconMap: Record<string, typeof FileJson> = {
    json: FileJson,
    csv: FileSpreadsheet,
    obsidian: FileText,
    markdown: FileText,
  };
  return iconMap[props.exporter.name] || FileType;
});

// Fallback color mappings for when ui_color is not available
const fallbackColorMap: Record<string, { glow: string; iconBg: string; icon: string }> = {
  json: { glow: 'bg-blue-400', iconBg: 'bg-blue-500/10', icon: 'text-blue-400' },
  csv: { glow: 'bg-green-400', iconBg: 'bg-green-500/10', icon: 'text-green-400' },
  obsidian: { glow: 'bg-purple-400', iconBg: 'bg-purple-500/10', icon: 'text-purple-400' },
  markdown: { glow: 'bg-orange-400', iconBg: 'bg-orange-500/10', icon: 'text-orange-400' },
};

// Get glow color - use metadata ui_color if available, fallback to hardcoded mapping
const glowColor = computed(() => {
  // If ui_color is available from metadata, we could use it with CSS custom properties
  // For now, fallback to the hardcoded mapping since Tailwind classes are static
  const fallback = fallbackColorMap[props.exporter.name];
  return fallback?.glow || 'bg-accent-primary';
});

// Get icon background color
const iconBgColor = computed(() => {
  const fallback = fallbackColorMap[props.exporter.name];
  return fallback?.iconBg || 'bg-accent-primary/10';
});

// Get icon color
const iconColor = computed(() => {
  const fallback = fallbackColorMap[props.exporter.name];
  return fallback?.icon || 'text-accent-primary';
});

// Get friendly name for exporter - use metadata if available, fallback to name capitalization
const displayName = computed(() => {
  return props.exporter.metadata?.display_name ||
    props.exporter.name.charAt(0).toUpperCase() + props.exporter.name.slice(1);
});

// Tooltip for disabled toggle
const toggleTooltip = computed(() => {
  if (!props.exporter.can_enable && !props.exporter.enabled) {
    return strings.settings.exports.configureRequired;
  }
  return props.exporter.enabled ? strings.settings.exports.disableExporter : strings.settings.exports.enableExporter;
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
      class="absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-0 blur-3xl transition-all duration-700"
      :class="[glowColor, selected ? 'opacity-30' : 'group-hover:opacity-20']"
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
          class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
          :class="iconBgColor"
        >
          <component
            :is="ExporterIcon"
            :size="22"
            :stroke-width="2"
            :class="iconColor"
          />
        </div>
        <div>
          <div class="text-base font-semibold text-text-primary transition-colors group-hover:text-accent-primary">
            {{ displayName }}
          </div>
          <div class="text-xs text-text-muted">.{{ exporter.file_extension }}</div>
        </div>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-muted line-clamp-2">
        {{ exporter.description }}
      </p>

      <!-- Toggle and feature badges -->
      <div class="flex items-center gap-3 pt-1">
        <!-- Toggle switch (left) -->
        <div
          @click.stop
          :title="toggleTooltip"
        >
          <ToggleSwitch
            :model-value="exporter.enabled"
            @update:model-value="handleToggle"
            :disabled="(!exporter.can_enable && !exporter.enabled) || isToggling"
            size="sm"
          />
        </div>

        <!-- Feature badges -->
        <div class="flex flex-wrap gap-2">
          <span
            v-if="exporter.supports_direct_export"
            class="inline-flex items-center gap-1.5 rounded-full bg-status-success/10 px-2.5 py-1 text-xs font-medium text-status-success"
          >
            <HardDrive :size="12" />
            {{ strings.settings.exports.features.directExport }}
          </span>
          <span
            v-if="exporter.config_schema.fields.length > 0"
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
