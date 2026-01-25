<script setup lang="ts">
/**
 * ConnectionSelector - Dropdown for selecting email connections
 *
 * Features:
 * - Fetches connections filtered by type
 * - Shows provider icon, name, and health indicator
 * - "+ Create New Connection" option at bottom
 * - Emits event for inline connection creation
 */
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { Icon } from '@iconify/vue';
import { connectionsApi } from '@/services/api';
import { ChevronDown, Plus, CheckCircle, AlertCircle, XCircle, Loader2 } from 'lucide-vue-next';
import type { Connection, ConnectionType } from '@/types/entities';
import { strings } from '@/i18n/en';

interface Props {
  /** The selected connection ID */
  modelValue?: number | null;
  /** Filter connections by type */
  connectionType?: ConnectionType;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Placeholder text when no connection selected */
  placeholder?: string;
}

interface Emits {
  (e: 'update:modelValue', value: number | null): void;
  (e: 'createNew'): void;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  connectionType: 'email_imap',
  disabled: false,
  placeholder: 'Select a connection...',
});

const emit = defineEmits<Emits>();

// Fetch connections filtered by type
const { data: connectionsData, isLoading } = useQuery({
  queryKey: ['connections', props.connectionType],
  queryFn: () => connectionsApi.list(props.connectionType),
  staleTime: 1000 * 60 * 2, // 2 minutes
});

const connections = computed(() => connectionsData.value?.items ?? []);

// Get the currently selected connection
const selectedConnection = computed(() => {
  if (!props.modelValue) return null;
  return connections.value.find(c => c.id === props.modelValue) ?? null;
});

// Provider icon mapping
const providerIcons: Record<string, string> = {
  gmail: 'mdi:gmail',
  outlook: 'mdi:microsoft-outlook',
  generic: 'mdi:email-outline',
};

function getProviderIcon(connection: Connection): string {
  return providerIcons[connection.provider ?? 'generic'] ?? providerIcons.generic;
}

// Health status configuration
type HealthStatus = 'healthy' | 'warning' | 'error' | 'unknown';

const healthConfig: Record<HealthStatus, { icon: typeof CheckCircle | null; color: string }> = {
  healthy: { icon: CheckCircle, color: 'text-green-400' },
  warning: { icon: AlertCircle, color: 'text-amber-400' },
  error: { icon: XCircle, color: 'text-red-400' },
  unknown: { icon: null, color: 'text-text-muted' },
};

function getHealthStatus(connection: Connection): HealthStatus {
  if (!connection.last_check_at) return 'unknown';
  if (connection.last_success_at && !connection.last_failure_at) return 'healthy';
  if (connection.last_failure_at) {
    if (!connection.last_success_at) return 'error';
    const lastSuccess = new Date(connection.last_success_at);
    const lastFailure = new Date(connection.last_failure_at);
    return lastFailure > lastSuccess ? 'error' : 'warning';
  }
  return 'healthy';
}

// Computed health info for selected connection to avoid repeated template calls
const selectedHealthInfo = computed(() => {
  if (!selectedConnection.value) return null;
  const status = getHealthStatus(selectedConnection.value);
  return healthConfig[status];
});

function handleSelect(connectionId: number | null) {
  emit('update:modelValue', connectionId);
}

function handleCreateNew() {
  emit('createNew');
}
</script>

<template>
  <div class="relative">
    <!-- Custom Select Dropdown -->
    <div class="group">
      <select
        :value="modelValue ?? ''"
        :disabled="disabled || isLoading"
        @change="handleSelect(($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
        class="w-full appearance-none rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 pr-10 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <!-- Placeholder option -->
        <option value="" :disabled="!modelValue">
          {{ isLoading ? strings.common.loading : placeholder }}
        </option>

        <!-- Connection options -->
        <option
          v-for="connection in connections"
          :key="connection.id"
          :value="connection.id"
        >
          {{ connection.name }}
        </option>
      </select>

      <!-- Dropdown icon -->
      <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
        <Loader2 v-if="isLoading" :size="16" class="animate-spin text-text-muted" />
        <ChevronDown v-else :size="16" class="text-text-muted" />
      </div>
    </div>

    <!-- Selected connection display (shows more details than native select) -->
    <div
      v-if="selectedConnection && !isLoading"
      class="mt-2 flex items-center justify-between rounded-lg border border-border-subtle bg-bg-base px-3 py-2"
    >
      <div class="flex items-center gap-2">
        <!-- Provider icon -->
        <Icon :icon="getProviderIcon(selectedConnection)" :width="18" :height="18" class="text-text-muted" />
        <!-- Name -->
        <span class="text-sm text-text-primary">{{ selectedConnection.name }}</span>
        <!-- Health indicator -->
        <component
          v-if="selectedHealthInfo?.icon"
          :is="selectedHealthInfo.icon"
          :size="14"
          :class="selectedHealthInfo.color"
        />
      </div>
      <!-- Source count -->
      <span v-if="selectedConnection.source_count > 0" class="text-xs text-text-muted">
        {{ strings.settings.email.connections.usedBy.replace('{count}', String(selectedConnection.source_count)) }}
      </span>
    </div>

    <!-- No connections message + Create button -->
    <div
      v-if="!isLoading && connections.length === 0"
      class="mt-2 rounded-lg border border-border-subtle border-dashed bg-bg-base p-4 text-center"
    >
      <p class="text-sm text-text-muted">{{ strings.settings.email.connections.empty }}</p>
      <button
        type="button"
        @click="handleCreateNew"
        class="mt-2 inline-flex items-center gap-1 text-sm font-medium text-accent-primary hover:text-accent-primary/80"
      >
        <Plus :size="14" />
        {{ strings.settings.email.connections.addConnection }}
      </button>
    </div>

    <!-- Create new connection link (when connections exist) -->
    <div v-else-if="!isLoading && connections.length > 0" class="mt-2">
      <button
        type="button"
        @click="handleCreateNew"
        class="inline-flex items-center gap-1 text-xs font-medium text-accent-primary hover:text-accent-primary/80"
      >
        <Plus :size="12" />
        {{ strings.settings.email.connections.addConnection }}
      </button>
    </div>
  </div>
</template>
