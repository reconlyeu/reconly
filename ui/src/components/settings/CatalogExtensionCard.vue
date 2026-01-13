<script setup lang="ts">
/**
 * Card for displaying an extension from the catalog.
 * Shows package info, verified badge, install status, and action buttons.
 * Type is indicated visually via icon color/shape with tooltip.
 */
import { computed } from 'vue';
import {
  ArrowRightFromLine,
  ArrowRightToLine,
  Cpu,
  Check,
  Download,
  Trash2,
  ExternalLink,
  ShieldCheck,
  Loader2,
} from 'lucide-vue-next';
import type { CatalogEntry } from '@/types/entities';
import { strings } from '@/i18n/en';

interface Props {
  entry: CatalogEntry;
  isInstalling?: boolean;
  isUninstalling?: boolean;
}

interface Emits {
  (e: 'install', entry: CatalogEntry): void;
  (e: 'uninstall', entry: CatalogEntry): void;
}

const props = withDefaults(defineProps<Props>(), {
  isInstalling: false,
  isUninstalling: false,
});

const emit = defineEmits<Emits>();

const handleInstall = () => {
  emit('install', props.entry);
};

const handleUninstall = () => {
  emit('uninstall', props.entry);
};

// Get type-specific icon styling
const typeIconConfig = computed(() => {
  const configMap: Record<string, { bg: string; text: string; label: string }> = {
    exporter: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Exporter' },
    fetcher: { bg: 'bg-purple-500/10', text: 'text-purple-400', label: 'Fetcher' },
    provider: { bg: 'bg-orange-500/10', text: 'text-orange-400', label: 'Provider' },
  };
  return configMap[props.entry.type] || { bg: 'bg-gray-500/10', text: 'text-gray-400', label: 'Extension' };
});

// Check if action is in progress
const isActionInProgress = computed(() => props.isInstalling || props.isUninstalling);
</script>

<template>
  <div
    class="group relative overflow-hidden rounded-2xl border bg-gradient-to-br from-bg-elevated to-bg-surface p-5 transition-all duration-300 border-border-subtle hover:border-border-default hover:shadow-xl hover:shadow-black/5"
  >
    <!-- Hover glow effect -->
    <div
      class="absolute inset-0 bg-gradient-to-br from-accent-primary/[0.02] to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
    />

    <!-- Installed badge (top-right) -->
    <div class="absolute right-3 top-3">
      <div
        v-if="entry.installed"
        class="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium bg-accent-primary/10 text-accent-primary border-accent-primary/20"
      >
        <Check :size="12" />
        {{ strings.settings.extensions.catalog.installed }}
      </div>
    </div>

    <div class="relative flex flex-col gap-3">
      <!-- Icon (type-specific) and name with verified badge -->
      <div class="flex items-start gap-3">
        <div
          class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
          :class="typeIconConfig.bg"
          :title="typeIconConfig.label"
        >
          <ArrowRightFromLine v-if="entry.type === 'exporter'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <ArrowRightToLine v-else-if="entry.type === 'fetcher'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <Cpu v-else-if="entry.type === 'provider'" :size="22" :stroke-width="2" :class="typeIconConfig.text" />
          <ArrowRightFromLine v-else :size="22" :stroke-width="2" :class="typeIconConfig.text" />
        </div>
        <div class="flex-1 min-w-0 pr-20">
          <div class="flex items-center gap-2">
            <div class="text-base font-semibold text-text-primary truncate">
              {{ entry.name }}
            </div>
            <!-- Verified badge (inline with title) -->
            <ShieldCheck
              v-if="entry.verified"
              :size="16"
              class="flex-shrink-0 text-green-400"
              :title="strings.settings.extensions.catalog.verified"
            />
          </div>
          <div class="flex items-center gap-2 text-xs text-text-muted">
            <span>{{ strings.settings.extensions.version.replace('{version}', entry.version) }}</span>
            <span>·</span>
            <span>{{ strings.settings.extensions.author.replace('{author}', entry.author) }}</span>
          </div>
        </div>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-muted line-clamp-2">
        {{ entry.description }}
      </p>

      <!-- Actions row -->
      <div class="flex items-center justify-between pt-1">
        <div class="flex items-center gap-2">
          <!-- Homepage link -->
          <a
            v-if="entry.homepage"
            :href="entry.homepage"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 rounded-full bg-bg-surface px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
          >
            <ExternalLink :size="12" />
            {{ strings.settings.extensions.homepage }}
          </a>

          <!-- PyPI link -->
          <a
            v-if="entry.pypi_url"
            :href="entry.pypi_url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 rounded-full bg-bg-surface px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
          >
            <ExternalLink :size="12" />
            PyPI
          </a>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center gap-2">
          <!-- Uninstall button (if installed) -->
          <button
            v-if="entry.installed"
            @click="handleUninstall"
            :disabled="isActionInProgress"
            class="inline-flex items-center gap-1.5 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="isUninstalling" :size="14" class="animate-spin" />
            <Trash2 v-else :size="14" />
            {{ isUninstalling ? strings.settings.extensions.catalog.uninstalling : strings.settings.extensions.catalog.uninstall }}
          </button>

          <!-- Install button (if not installed) -->
          <button
            v-else
            @click="handleInstall"
            :disabled="isActionInProgress"
            class="inline-flex items-center gap-1.5 rounded-lg bg-accent-primary/10 px-3 py-1.5 text-xs font-medium text-accent-primary hover:bg-accent-primary/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="isInstalling" :size="14" class="animate-spin" />
            <Download v-else :size="14" />
            {{ isInstalling ? strings.settings.extensions.catalog.installing : strings.settings.extensions.catalog.install }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
