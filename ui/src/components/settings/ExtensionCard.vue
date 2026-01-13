<script setup lang="ts">
/**
 * Card for displaying an installed extension.
 * Shows metadata, activation status, and toggle controls.
 * Type is indicated visually via icon color/shape with tooltip.
 */
import { computed } from 'vue';
import {
  ArrowRightFromLine,
  ArrowRightToLine,
  Cpu,
  Check,
  X,
  AlertCircle,
  AlertTriangle,
  ExternalLink,
  Settings,
} from 'lucide-vue-next';
import type { Extension } from '@/types/entities';
import { strings } from '@/i18n/en';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import { useSettingsNavigation } from '@/composables/useSettingsNavigation';

interface Props {
  extension: Extension;
  isToggling?: boolean;
}

interface Emits {
  (e: 'toggle', name: string, type: string, enabled: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  isToggling: false,
});

const emit = defineEmits<Emits>();

function handleToggle(enabled: boolean): void {
  emit('toggle', props.extension.name, props.extension.type, enabled);
}

// Status configuration
type StatusType = 'active' | 'needs_config' | 'disabled' | 'load_error';

const status = computed<StatusType>(() => {
  const { enabled, is_configured, load_error } = props.extension;
  if (load_error) return 'load_error';
  if (enabled && is_configured) return 'active';
  if (!is_configured) return 'needs_config';
  return 'disabled';
});

const statusConfig = computed(() => {
  const configs = {
    active: {
      label: strings.settings.extensions.status.active,
      color: 'bg-green-500/10 text-green-400 border-green-500/20',
      icon: Check,
      dotColor: 'bg-green-500',
    },
    needs_config: {
      label: strings.settings.extensions.status.needsConfig,
      color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      icon: AlertCircle,
      dotColor: 'bg-amber-500',
    },
    disabled: {
      label: strings.settings.extensions.status.disabled,
      color: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
      icon: X,
      dotColor: 'bg-gray-500',
    },
    load_error: {
      label: strings.settings.extensions.status.loadError,
      color: 'bg-red-500/10 text-red-400 border-red-500/20',
      icon: AlertTriangle,
      dotColor: 'bg-red-500',
    },
  };
  return configs[status.value];
});

// Get type-specific icon styling
const typeIconConfig = computed(() => {
  const configMap: Record<string, { bg: string; text: string; label: string }> = {
    exporter: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Exporter' },
    fetcher: { bg: 'bg-purple-500/10', text: 'text-purple-400', label: 'Fetcher' },
    provider: { bg: 'bg-orange-500/10', text: 'text-orange-400', label: 'Provider' },
  };
  return configMap[props.extension.type] || { bg: 'bg-gray-500/10', text: 'text-gray-400', label: 'Extension' };
});

// Tooltip for disabled toggle
const toggleTooltip = computed(() => {
  if (props.extension.load_error) {
    return 'Extension failed to load';
  }
  if (!props.extension.can_enable && !props.extension.enabled) {
    return 'Configure required fields first';
  }
  return props.extension.enabled
    ? strings.settings.extensions.disable
    : strings.settings.extensions.enable;
});

// Has configurable fields (uses config_api instead of config_schema)
const hasConfig = computed(() => {
  return !!props.extension.config_api;
});

// Navigation to configure the extension
const { navigateTo } = useSettingsNavigation();

// Check if this extension type can be configured (providers use env vars)
const canConfigure = computed(() => {
  return props.extension.type === 'exporter' || props.extension.type === 'fetcher';
});

// Navigate to the appropriate tab to configure this extension
const handleConfigure = () => {
  if (props.extension.type === 'exporter') {
    navigateTo({ tab: 'exports', exporter: props.extension.name });
  } else if (props.extension.type === 'fetcher') {
    navigateTo({ tab: 'fetchers', fetcher: props.extension.name });
  }
};
</script>

<template>
  <div
    class="group relative overflow-hidden rounded-2xl border bg-gradient-to-br from-bg-elevated to-bg-surface p-5 transition-all duration-300 border-border-subtle hover:border-border-default hover:shadow-xl hover:shadow-black/5"
  >
    <!-- Hover glow effect -->
    <div
      class="absolute inset-0 bg-gradient-to-br from-accent-primary/[0.02] to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
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
      <!-- Icon (type-specific) and name -->
      <div class="flex items-start gap-3">
        <div
          class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
          :class="typeIconConfig.bg"
          :title="typeIconConfig.label"
        >
          <ArrowRightFromLine v-if="extension.type === 'exporter'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <ArrowRightToLine v-else-if="extension.type === 'fetcher'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <Cpu v-else-if="extension.type === 'provider'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <ArrowRightFromLine v-else :size="22" :stroke-width="2" :class="typeIconConfig.text" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-base font-semibold text-text-primary truncate">
            {{ extension.metadata.name }}
          </div>
          <div class="flex items-center gap-2 text-xs text-text-muted">
            <span>{{ strings.settings.extensions.version.replace('{version}', extension.metadata.version) }}</span>
            <span>·</span>
            <span>{{ strings.settings.extensions.author.replace('{author}', extension.metadata.author) }}</span>
          </div>
        </div>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-muted line-clamp-2">
        {{ extension.metadata.description }}
      </p>

      <!-- Load error message -->
      <div
        v-if="extension.load_error"
        class="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400"
      >
        <div class="flex items-start gap-2">
          <AlertTriangle :size="16" class="mt-0.5 flex-shrink-0" />
          <span>{{ extension.load_error }}</span>
        </div>
      </div>

      <!-- Actions row -->
      <div class="flex items-center gap-3 pt-1">
        <!-- Toggle switch (left) -->
        <div
          @click.stop
          :title="toggleTooltip"
        >
          <ToggleSwitch
            :model-value="extension.enabled"
            @update:model-value="handleToggle"
            :disabled="(!extension.can_enable && !extension.enabled) || extension.load_error !== null || isToggling"
            size="sm"
          />
        </div>

        <!-- Links -->
        <div class="flex items-center gap-2">
          <!-- Homepage link -->
          <a
            v-if="extension.metadata.homepage"
            :href="extension.metadata.homepage"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 rounded-full bg-bg-surface px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
          >
            <ExternalLink :size="12" />
            {{ strings.settings.extensions.homepage }}
          </a>

          <!-- Configure button (exporters and fetchers - providers use env vars) -->
          <button
            v-if="hasConfig && canConfigure"
            @click="handleConfigure"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-full bg-bg-surface px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
          >
            <Settings :size="12" />
            {{ strings.settings.extensions.configure }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
