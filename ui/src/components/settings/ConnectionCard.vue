<script setup lang="ts">
/**
 * Connection card component for displaying email IMAP connections.
 * Shows connection name, provider, health status, and usage count.
 * Provides actions dropdown for Edit, Test, and Delete.
 */
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { MoreVertical, Edit2, TestTube, Trash2, Loader2 } from 'lucide-vue-next';
import { Icon } from '@iconify/vue';
import { strings } from '@/i18n/en';
import type { Connection, ConnectionProvider } from '@/types/entities';

interface Props {
  connection: Connection;
  isTesting?: boolean;
}

interface Emits {
  (e: 'edit', connection: Connection): void;
  (e: 'test', connection: Connection): void;
  (e: 'delete', connection: Connection): void;
}

const props = withDefaults(defineProps<Props>(), {
  isTesting: false,
});

const emit = defineEmits<Emits>();

const isMenuOpen = ref(false);
const menuRef = ref<HTMLDivElement | null>(null);

// Provider icons
const providerIcons: Record<ConnectionProvider, string> = {
  gmail: 'mdi:gmail',
  outlook: 'mdi:microsoft-outlook',
  generic: 'mdi:email-outline',
};

// Provider colors
const providerColors: Record<ConnectionProvider, { bg: string; text: string; glow: string }> = {
  gmail: { bg: 'bg-red-500/10', text: 'text-red-400', glow: 'bg-red-500' },
  outlook: { bg: 'bg-blue-500/10', text: 'text-blue-400', glow: 'bg-blue-500' },
  generic: { bg: 'bg-purple-500/10', text: 'text-purple-400', glow: 'bg-purple-500' },
};

/**
 * Determine health status based on last_success_at and last_failure_at.
 * - healthy: last success is more recent than last failure, or no failures
 * - warning: never checked (no success or failure timestamps)
 * - error: last failure is more recent than last success, or never succeeded
 */
type HealthStatus = 'healthy' | 'warning' | 'error';

const healthStatus = computed<HealthStatus>(() => {
  const { last_success_at, last_failure_at } = props.connection;

  // Never checked yet
  if (!last_success_at && !last_failure_at) {
    return 'warning';
  }

  // No failures, or success is more recent than failure
  if (!last_failure_at) {
    return 'healthy';
  }

  if (!last_success_at) {
    return 'error';
  }

  // Compare timestamps when both exist
  return new Date(last_success_at).getTime() >= new Date(last_failure_at).getTime()
    ? 'healthy'
    : 'error';
});

const healthConfig = computed(() => {
  const configs = {
    healthy: {
      label: strings.settings.email.connections.healthy,
      dotColor: 'bg-green-500',
      animate: false,
    },
    warning: {
      label: strings.settings.email.connections.warning,
      dotColor: 'bg-amber-500',
      animate: true,
    },
    error: {
      label: strings.settings.email.connections.error,
      dotColor: 'bg-red-500',
      animate: true,
    },
  };
  return configs[healthStatus.value];
});

const provider = computed(() => props.connection.provider || 'generic');
const providerIcon = computed(() => providerIcons[provider.value]);
const providerColor = computed(() => providerColors[provider.value]);
const providerLabel = computed(() => {
  const labels = strings.settings.email.connections.providers;
  return labels[provider.value as keyof typeof labels] || provider.value;
});

const sourceCountText = computed(() => {
  const count = props.connection.source_count || 0;
  if (count === 0) {
    return strings.settings.email.connections.noSources;
  }
  return strings.settings.email.connections.usedBy.replace('{count}', String(count));
});

// Actions
const handleEdit = () => {
  isMenuOpen.value = false;
  emit('edit', props.connection);
};

const handleTest = () => {
  isMenuOpen.value = false;
  emit('test', props.connection);
};

const handleDelete = () => {
  isMenuOpen.value = false;
  emit('delete', props.connection);
};

const toggleMenu = (event: Event) => {
  event.stopPropagation();
  isMenuOpen.value = !isMenuOpen.value;
};

// Close menu on click outside
const handleClickOutside = (event: MouseEvent) => {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    isMenuOpen.value = false;
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div
    class="group relative rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated to-bg-surface p-5 transition-all duration-300 hover:border-border-default hover:shadow-xl hover:shadow-black/5"
  >
    <!-- Decorative effects (clipped to card bounds) -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl">
      <!-- Hover glow effect -->
      <div
        class="absolute inset-0 bg-gradient-to-br from-accent-primary/[0.02] to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
      />
      <!-- Corner orb -->
      <div
        class="absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-0 blur-3xl transition-all duration-700 group-hover:opacity-20"
        :class="providerColor.glow"
      />
    </div>

    <!-- Health indicator (top-right) -->
    <div class="absolute right-12 top-4 flex items-center gap-2">
      <div
        class="h-2.5 w-2.5 rounded-full"
        :class="[healthConfig.dotColor, { 'animate-pulse': healthConfig.animate }]"
        :title="healthConfig.label"
      />
    </div>

    <!-- Actions menu (top-right) -->
    <div ref="menuRef" class="absolute right-2 top-2 z-10">
      <button
        type="button"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
        @click="toggleMenu"
      >
        <MoreVertical :size="16" />
      </button>

      <!-- Dropdown menu -->
      <Transition
        enter-active-class="transition ease-out duration-100"
        enter-from-class="transform opacity-0 scale-95"
        enter-to-class="transform opacity-100 scale-100"
        leave-active-class="transition ease-in duration-75"
        leave-from-class="transform opacity-100 scale-100"
        leave-to-class="transform opacity-0 scale-95"
      >
        <div
          v-if="isMenuOpen"
          class="absolute right-0 top-full z-10 mt-1 min-w-[140px] overflow-hidden rounded-lg border border-border-subtle bg-bg-elevated shadow-lg"
        >
          <ul class="py-1">
            <li>
              <button
                type="button"
                class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
                @click="handleEdit"
              >
                <Edit2 :size="14" class="text-text-muted" />
                {{ strings.settings.email.connections.edit }}
              </button>
            </li>
            <li>
              <button
                type="button"
                class="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
                :disabled="isTesting"
                @click="handleTest"
              >
                <Loader2 v-if="isTesting" :size="14" class="animate-spin text-text-muted" />
                <TestTube v-else :size="14" class="text-text-muted" />
                {{ isTesting ? strings.settings.email.connections.testing : strings.settings.email.connections.test }}
              </button>
            </li>
            <li>
              <button
                type="button"
                class="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400 transition-colors hover:bg-red-500/10"
                @click="handleDelete"
              >
                <Trash2 :size="14" />
                {{ strings.settings.email.connections.delete }}
              </button>
            </li>
          </ul>
        </div>
      </Transition>
    </div>

    <div class="relative flex flex-col gap-3">
      <!-- Icon and name -->
      <div class="flex items-center gap-3">
        <div
          class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
          :class="providerColor.bg"
        >
          <Icon
            :icon="providerIcon"
            :width="22"
            :height="22"
            :class="providerColor.text"
          />
        </div>
        <div class="pr-10">
          <div class="text-base font-semibold text-text-primary transition-colors group-hover:text-accent-primary">
            {{ connection.name }}
          </div>
          <div class="text-xs text-text-muted">{{ providerLabel }}</div>
        </div>
      </div>

      <!-- Usage info -->
      <div class="flex items-center gap-4 pt-1 text-xs text-text-muted">
        <span>{{ sourceCountText }}</span>
      </div>
    </div>
  </div>
</template>
