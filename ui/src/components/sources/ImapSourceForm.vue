<script setup lang="ts">
/**
 * IMAP source configuration form component.
 * Used within SourceForm for imap-type sources.
 * Supports OAuth providers (Gmail, Outlook) and Generic IMAP.
 */
import { ref, computed, watch } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { oauthApi } from '@/services/api';
import type { IMAPProvider, SourceConfig } from '@/types/entities';
import { Mail, Lock, Server, Folder, User, Eye, EyeOff, Loader2, ChevronDown, Filter } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  /** Whether the form is in loading/saving state */
  isLoading?: boolean;
  /** Whether we're editing an existing source (vs creating new) */
  isEditMode?: boolean;
}

const props = defineProps<Props>();

const config = defineModel<SourceConfig>('config', { default: () => ({}) });
const provider = defineModel<IMAPProvider>('provider', { required: true });
const folders = defineModel<string>('folders', { default: '' });
const fromFilter = defineModel<string>('fromFilter', { default: '' });
const subjectFilter = defineModel<string>('subjectFilter', { default: '' });

// Generic IMAP specific fields
const imapHost = defineModel<string>('imapHost', { default: '' });
const imapPort = defineModel<number>('imapPort', { default: 993 });
const imapUsername = defineModel<string>('imapUsername', { default: '' });
const imapPassword = defineModel<string>('imapPassword', { default: '' });
const imapUseSsl = defineModel<boolean>('imapUseSsl', { default: true });

// Local state
const showPassword = ref(false);
// Server settings expanded on create, collapsed on edit
const showServerSettings = ref(!props.isEditMode);
// Filters always collapsed by default
const showFilters = ref(false);

// Check if server settings are configured (to show badge when collapsed)
const hasServerSettings = computed(() => {
  return Boolean(imapHost.value || imapUsername.value);
});

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

// Watch provider changes to reset fields
watch(provider, (newProvider) => {
  if (newProvider !== 'generic') {
    // Clear generic IMAP fields when switching to OAuth provider
    imapHost.value = '';
    imapPort.value = 993;
    imapUsername.value = '';
    imapPassword.value = '';
    imapUseSsl.value = true;
  }
});

// Auto-select 'generic' if OAuth providers are not configured (on create only)
watch(oauthProviders, (providers) => {
  if (props.isEditMode) return; // Don't change selection when editing
  if (!providers) return;

  const gmailConfigured = providers.providers.find(p => p.provider === 'gmail')?.configured ?? false;
  const outlookConfigured = providers.providers.find(p => p.provider === 'outlook')?.configured ?? false;

  // If current selection is an unconfigured OAuth provider, switch to generic
  if (provider.value === 'gmail' && !gmailConfigured) {
    provider.value = outlookConfigured ? 'outlook' : 'generic';
  } else if (provider.value === 'outlook' && !outlookConfigured) {
    provider.value = gmailConfigured ? 'gmail' : 'generic';
  }
}, { immediate: true });
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

    <!-- Collapsible Generic IMAP Server Settings -->
    <div v-if="provider === 'generic'" class="rounded-lg border border-border-subtle bg-bg-surface">
      <!-- Toggle Header -->
      <button
        type="button"
        @click="showServerSettings = !showServerSettings"
        class="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-bg-hover rounded-lg"
      >
        <div class="flex items-center gap-2">
          <Server :size="16" class="text-text-muted" />
          <span class="text-sm font-medium text-text-primary">{{ strings.sources.imap.sections.serverSettings }}</span>
          <span v-if="hasServerSettings && !showServerSettings" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
            {{ strings.sources.imap.configured }}
          </span>
        </div>
        <ChevronDown
          :size="16"
          class="text-text-muted transition-transform"
          :class="showServerSettings && 'rotate-180'"
        />
      </button>

      <!-- Server Settings Content -->
      <Transition name="slide">
        <div v-if="showServerSettings" class="space-y-4 border-t border-border-subtle p-3">
          <!-- IMAP Server -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              {{ strings.sources.imap.fields.host }}
            </label>
            <input
              v-model="imapHost"
              type="text"
              :placeholder="strings.sources.imap.placeholders.host"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Port & SSL Row -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-text-primary">
                {{ strings.sources.imap.fields.port }}
              </label>
              <input
                v-model.number="imapPort"
                type="number"
                min="1"
                max="65535"
                class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-sm font-medium text-text-primary">
                {{ strings.sources.imap.fields.ssl }}
              </label>
              <button
                type="button"
                @click="imapUseSsl = !imapUseSsl"
                class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors"
                :class="imapUseSsl
                  ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                  : 'border-border-subtle bg-bg-base text-text-muted'"
              >
                <span>{{ imapUseSsl ? strings.common.enabled : strings.common.disabled }}</span>
                <Lock :size="14" />
              </button>
            </div>
          </div>

          <!-- Username -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              <User :size="14" class="mr-1 inline" />
              {{ strings.sources.imap.fields.username }}
            </label>
            <input
              v-model="imapUsername"
              type="text"
              :placeholder="strings.sources.imap.placeholders.username"
              autocomplete="username"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Password -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              <Lock :size="14" class="mr-1 inline" />
              {{ strings.sources.imap.fields.password }}
            </label>
            <div class="relative">
              <input
                v-model="imapPassword"
                :type="showPassword ? 'text' : 'password'"
                :placeholder="strings.sources.imap.placeholders.password"
                autocomplete="current-password"
                class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 pr-10 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted transition-colors hover:text-text-primary"
              >
                <Eye v-if="!showPassword" :size="16" />
                <EyeOff v-else :size="16" />
              </button>
            </div>
            <p class="mt-1 text-xs text-text-muted">
              {{ strings.sources.imap.hints.passwordEncrypted }}
            </p>
          </div>
        </div>
      </Transition>
    </div>

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
