<script setup lang="ts">
import { computed } from 'vue';
import { Rss, Youtube, Globe, BookOpen, Edit, Trash2, Mail, Bot, RefreshCw, Server } from 'lucide-vue-next';
import type { Source } from '@/types/entities';
import { useConfirm } from '@/composables/useConfirm';
import {
  getAuthStatusConfig,
  needsReauthentication,
  handleReauthenticate,
  getReauthButtonText,
  getReauthButtonTitle,
} from '@/composables/useAuthStatus';
import BaseCard from '@/components/common/BaseCard.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import { strings } from '@/i18n/en';

interface Props {
  source: Source;
}

interface Emits {
  (e: 'toggle', sourceId: number, enabled: boolean): void;
  (e: 'edit', source: Source): void;
  (e: 'delete', sourceId: number): void;
  (e: 'reauthenticate', source: Source): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// Detect if YouTube URL is a channel
const isYouTubeChannel = (url: string): boolean => {
  const channelPatterns = [
    /youtube\.com\/channel\/UC[a-zA-Z0-9_-]+/i,
    /youtube\.com\/@[a-zA-Z0-9_.-]+/i,
    /youtube\.com\/c\/[a-zA-Z0-9_.-]+/i,
    /youtube\.com\/user\/[a-zA-Z0-9_.-]+/i,
  ];
  return channelPatterns.some(pattern => pattern.test(url));
};

const typeConfig = computed(() => {
  // Special handling for YouTube to distinguish video vs channel
  if (props.source.type === 'youtube') {
    const isChannel = isYouTubeChannel(props.source.url);
    return {
      icon: Youtube,
      label: isChannel ? `${strings.sources.types.youtube} Channel` : `${strings.sources.types.youtube} Video`,
      color: 'text-red-500',
      bgColor: 'bg-red-500/10',
      glow: 'error' as const,
    };
  }

  const configs = {
    rss: {
      icon: Rss,
      label: `${strings.sources.types.rss} Feed`,
      color: 'text-orange-400',
      bgColor: 'bg-orange-400/10',
      glow: 'orange' as const,
    },
    youtube: {
      icon: Youtube,
      label: strings.sources.types.youtube,
      color: 'text-red-500',
      bgColor: 'bg-red-500/10',
      glow: 'error' as const,
    },
    website: {
      icon: Globe,
      label: strings.sources.types.website,
      color: 'text-blue-400',
      bgColor: 'bg-blue-400/10',
      glow: 'blue' as const,
    },
    blog: {
      icon: BookOpen,
      label: strings.sources.types.blog,
      color: 'text-green-400',
      bgColor: 'bg-green-400/10',
      glow: 'success' as const,
    },
    imap: {
      icon: Mail,
      label: `${strings.sources.types.imap} (IMAP)`,
      color: 'text-purple-400',
      bgColor: 'bg-purple-400/10',
      glow: 'purple' as const,
    },
    agent: {
      icon: Bot,
      label: strings.sources.types.agent,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-400/10',
      glow: 'blue' as const,
    },
  };
  return configs[props.source.type as keyof typeof configs] || configs.rss;
});

// Auth status configuration for IMAP sources
const authStatusConfig = computed(() => {
  if (props.source.type !== 'imap') return null;
  return getAuthStatusConfig(props.source.auth_status);
});

// Handle re-authentication for failed or pending OAuth
const onReauthenticate = async () => {
  const isOAuthRedirect = await handleReauthenticate(props.source);
  if (!isOAuthRedirect) {
    // For generic IMAP, emit event to edit the source
    emit('reauthenticate', props.source);
  }
};

const handleToggle = (value: boolean) => {
  emit('toggle', props.source.id, value);
};

const handleEdit = () => {
  emit('edit', props.source);
};

const handleDelete = () => {
  const { confirmDelete } = useConfirm();
  if (confirmDelete(props.source.name, 'source')) {
    emit('delete', props.source.id);
  }
};
</script>

<template>
  <BaseCard :glow-color="typeConfig.glow">
    <template #header>
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <!-- Type Icon -->
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
            :class="typeConfig.bgColor"
          >
            <component :is="typeConfig.icon" :class="typeConfig.color" :size="22" :stroke-width="2" />
          </div>

          <!-- Type Label -->
          <div>
            <div class="text-xs font-medium uppercase tracking-wider text-text-muted">
              {{ typeConfig.label }}
            </div>
          </div>
        </div>

        <!-- Status Badges -->
        <div class="flex items-center gap-2">
          <!-- Auth Status Badge (for IMAP sources) -->
          <div
            v-if="authStatusConfig"
            class="rounded-full px-3 py-1 text-xs font-medium"
            :class="[authStatusConfig.bgColor, authStatusConfig.textColor]"
          >
            {{ authStatusConfig.label }}
          </div>

          <!-- Enabled/Disabled Badge -->
          <div
            class="rounded-full px-3 py-1 text-xs font-medium transition-colors duration-300"
            :class="
              source.enabled
                ? 'bg-status-success/10 text-status-success'
                : 'bg-text-muted/10 text-text-muted'
            "
          >
            {{ source.enabled ? strings.sources.status.active : strings.sources.status.disabled }}
          </div>
        </div>
      </div>
    </template>

    <!-- Source Name -->
    <h3 class="mb-2 text-lg font-semibold text-text-primary transition-colors duration-300 group-hover:text-accent-primary">
      {{ source.name }}
    </h3>

    <!-- Source URL -->
    <div class="flex items-center gap-2">
      <p class="truncate text-sm text-text-muted">
        {{ source.url }}
      </p>
    </div>

    <!-- Connection Name (for sources using a Connection) -->
    <div v-if="source.connection_name" class="mt-1 flex items-center gap-1.5">
      <Server :size="12" class="text-text-muted" />
      <span class="text-xs text-text-muted">
        {{ strings.sources.viaConnection.replace('{name}', source.connection_name) }}
      </span>
    </div>

    <template #footer>
      <div class="flex items-center justify-between">
        <!-- Toggle Switch -->
        <ToggleSwitch
          :model-value="source.enabled"
          @update:model-value="handleToggle"
          :label="strings.sources.actions.toggle"
        />

        <!-- Action Buttons -->
        <div class="flex gap-2">
          <!-- Re-authenticate Button (for IMAP sources with pending/failed auth) -->
          <button
            v-if="needsReauthentication(source)"
            @click="onReauthenticate"
            class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-300"
            :class="source.auth_status === 'pending_oauth'
              ? 'bg-amber-500/10 text-amber-500 hover:bg-amber-500/20'
              : 'bg-status-failed/10 text-status-failed hover:bg-status-failed/20'"
            :title="getReauthButtonTitle(source.auth_status)"
          >
            <RefreshCw :size="14" :stroke-width="2" />
            {{ getReauthButtonText(source.auth_status) }}
          </button>

          <button
            @click="handleEdit"
            class="rounded-lg p-2 text-text-muted transition-all duration-300 hover:bg-bg-hover hover:text-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.sources.actions.edit"
          >
            <Edit :size="18" :stroke-width="2" />
          </button>
          <button
            @click="handleDelete"
            class="rounded-lg p-2 text-text-muted transition-all duration-300 hover:bg-status-failed/10 hover:text-status-failed focus:outline-none focus:ring-2 focus:ring-status-failed focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.sources.actions.delete"
          >
            <Trash2 :size="18" :stroke-width="2" />
          </button>
        </div>
      </div>
    </template>
  </BaseCard>
</template>
