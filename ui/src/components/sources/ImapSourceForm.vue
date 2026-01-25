<script setup lang="ts">
/**
 * IMAP source configuration form component.
 * Used within SourceForm for imap-type sources.
 * Supports OAuth providers (Gmail, Outlook) and Generic IMAP via Connections.
 *
 * For generic IMAP provider, users must select an existing Connection
 * or create a new one inline. Credentials are stored in the Connection,
 * not directly on the Source.
 */
import { ref, computed, watch } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { oauthApi } from '@/services/api';
import type { IMAPProvider } from '@/types/entities';
import { Mail, Lock, Server, Folder, Loader2, ChevronDown, Filter } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import ConnectionSelector from './ConnectionSelector.vue';
import ConnectionModal from '@/components/settings/ConnectionModal.vue';

interface Props {
  /** Whether the form is in loading/saving state */
  isLoading?: boolean;
  /** Whether we're editing an existing source (vs creating new) */
  isEditMode?: boolean;
}

const props = defineProps<Props>();

const provider = defineModel<IMAPProvider>('provider', { required: true });
const connectionId = defineModel<number | null>('connectionId', { default: null });
const folders = defineModel<string>('folders', { default: '' });
const fromFilter = defineModel<string>('fromFilter', { default: '' });
const subjectFilter = defineModel<string>('subjectFilter', { default: '' });

// Local state
// Filters always collapsed by default
const showFilters = ref(false);
// Connection modal state
const showConnectionModal = ref(false);

// Check if any filters are configured (to show badge)
const hasFilters = computed(() => {
  return Boolean(folders.value || fromFilter.value || subjectFilter.value);
});

// Fetch OAuth providers to check configuration status
const { data: oauthProviders, isLoading: isLoadingProviders } = useQuery({
  queryKey: ['oauth-providers'],
  queryFn: () => oauthApi.getProviders(),
  staleTime: 1000 * 60 * 5, // 5 minutes
});

// Check if specific provider is configured
const isGmailConfigured = computed(() => {
  return oauthProviders.value?.providers.find(p => p.provider === 'gmail')?.configured ?? false;
});

const isOutlookConfigured = computed(() => {
  return oauthProviders.value?.providers.find(p => p.provider === 'outlook')?.configured ?? false;
});

// Provider display info
const providerInfo = computed(() => {
  const providers: Record<IMAPProvider, { name: string; icon: string; description: string }> = {
    gmail: {
      name: strings.sources.imap.providers.gmail,
      icon: 'https://www.google.com/gmail/about/static-2.0/images/logo-gmail.png',
      description: strings.sources.imap.providerDescriptions.gmail,
    },
    outlook: {
      name: strings.sources.imap.providers.outlook,
      icon: 'https://upload.wikimedia.org/wikipedia/commons/d/df/Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg',
      description: strings.sources.imap.providerDescriptions.outlook,
    },
    generic: {
      name: strings.sources.imap.providers.generic,
      icon: '',
      description: strings.sources.imap.providerDescriptions.generic,
    },
  };
  return providers[provider.value] || providers.generic;
});

// Watch provider changes to clear connection when switching to OAuth
watch(provider, (newProvider) => {
  if (newProvider !== 'generic') {
    // Clear connection_id when switching to OAuth provider
    connectionId.value = null;
  }
});

// Auto-select 'generic' if OAuth providers are not configured (on create only)
watch(oauthProviders, () => {
  if (props.isEditMode) return;

  // If current selection is an unconfigured OAuth provider, switch to an available option
  if (provider.value === 'gmail' && !isGmailConfigured.value) {
    provider.value = isOutlookConfigured.value ? 'outlook' : 'generic';
  } else if (provider.value === 'outlook' && !isOutlookConfigured.value) {
    provider.value = isGmailConfigured.value ? 'gmail' : 'generic';
  }
}, { immediate: true });

// Handle new connection created via modal
function handleConnectionSaved(connection: { id: number }) {
  connectionId.value = connection.id;
  showConnectionModal.value = false;
}
</script>

<template>
  <div class="space-y-6">
    <!-- Provider Selection (compact) -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        {{ strings.sources.imap.fields.provider }}
      </label>

      <div class="flex gap-2">
        <!-- Gmail Option -->
        <button
          type="button"
          @click="provider = 'gmail'"
          class="relative flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 transition-all"
          :class="[
            provider === 'gmail'
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover',
            !isGmailConfigured && 'opacity-50'
          ]"
          :disabled="!isGmailConfigured"
        >
          <Mail :size="16" class="text-red-500" />
          <span class="text-sm font-medium text-text-primary">{{ strings.sources.imap.providers.gmail }}</span>
        </button>

        <!-- Outlook Option -->
        <button
          type="button"
          @click="provider = 'outlook'"
          class="relative flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 transition-all"
          :class="[
            provider === 'outlook'
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover',
            !isOutlookConfigured && 'opacity-50'
          ]"
          :disabled="!isOutlookConfigured"
        >
          <Mail :size="16" class="text-blue-500" />
          <span class="text-sm font-medium text-text-primary">{{ strings.sources.imap.providers.outlook }}</span>
        </button>

        <!-- Generic IMAP Option -->
        <button
          type="button"
          @click="provider = 'generic'"
          class="relative flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 transition-all"
          :class="provider === 'generic'
            ? 'border-accent-primary bg-accent-primary/10'
            : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover'"
        >
          <Server :size="16" class="text-text-muted" />
          <span class="text-sm font-medium text-text-primary">{{ strings.sources.imap.providers.generic }}</span>
        </button>
      </div>

      <!-- Status indicators -->
      <div class="mt-2 flex items-center gap-3 text-xs text-text-muted">
        <Loader2 v-if="isLoadingProviders" :size="14" class="animate-spin" />
        <span v-else-if="!isGmailConfigured && !isOutlookConfigured">
          {{ strings.sources.imap.oauthNotConfigured }}
        </span>
        <span v-else>{{ providerInfo.description }}</span>
      </div>
    </div>

    <!-- OAuth Provider Info (Gmail/Outlook) -->
    <div v-if="provider !== 'generic'" class="rounded-lg border border-border-subtle bg-bg-surface p-4">
      <div class="flex items-start gap-3">
        <Lock :size="20" class="mt-0.5 flex-shrink-0 text-accent-primary" />
        <div>
          <h4 class="text-sm font-medium text-text-primary">{{ strings.sources.imap.oauth.title }}</h4>
          <p class="mt-1 text-xs text-text-muted">
            {{ strings.sources.imap.oauth.message.replace('{provider}', provider === 'gmail' ? 'Google' : 'Microsoft') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Connection Selection for Generic IMAP -->
    <div v-if="provider === 'generic'" class="rounded-lg border border-border-subtle bg-bg-surface p-4">
      <div class="flex items-center gap-2 mb-3">
        <Server :size="16" class="text-text-muted" />
        <label class="text-sm font-medium text-text-primary">
          {{ strings.sources.imap.connection.label }}
        </label>
      </div>
      <p class="text-xs text-text-muted mb-3">
        {{ strings.sources.imap.connection.description }}
      </p>
      <ConnectionSelector
        v-model="connectionId"
        connection-type="email_imap"
        :placeholder="strings.sources.imap.connection.placeholder"
        @create-new="showConnectionModal = true"
      />
    </div>

    <!-- Connection Modal for inline creation -->
    <ConnectionModal
      :is-open="showConnectionModal"
      @close="showConnectionModal = false"
      @saved="handleConnectionSaved"
    />

    <!-- Collapsible Email Filtering Options -->
    <div class="rounded-lg border border-border-subtle bg-bg-surface">
      <!-- Toggle Header -->
      <button
        type="button"
        @click="showFilters = !showFilters"
        class="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-bg-hover rounded-lg"
      >
        <div class="flex items-center gap-2">
          <Filter :size="16" class="text-text-muted" />
          <span class="text-sm font-medium text-text-primary">{{ strings.sources.imap.sections.emailFilters }}</span>
          <span v-if="hasFilters" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
            {{ strings.sources.imap.configured }}
          </span>
        </div>
        <ChevronDown
          :size="16"
          class="text-text-muted transition-transform"
          :class="showFilters && 'rotate-180'"
        />
      </button>

      <!-- Filter Content -->
      <Transition name="slide">
        <div v-if="showFilters" class="space-y-4 border-t border-border-subtle p-3">
          <!-- Folders -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              <Folder :size="14" class="mr-1 inline" />
              {{ strings.sources.imap.fields.folders }}
            </label>
            <input
              v-model="folders"
              type="text"
              :placeholder="strings.sources.imap.placeholders.folders"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
            <p class="mt-1 text-xs text-text-muted">
              {{ strings.sources.imap.hints.folders }}
            </p>
          </div>

          <!-- From Filter -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              {{ strings.sources.imap.fields.senderFilter }}
            </label>
            <input
              v-model="fromFilter"
              type="text"
              :placeholder="strings.sources.imap.placeholders.senderFilter"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Subject Filter -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              {{ strings.sources.imap.fields.subjectFilter }}
            </label>
            <input
              v-model="subjectFilter"
              type="text"
              :placeholder="strings.sources.imap.placeholders.subjectFilter"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
/* Slide transitions for filter section */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
