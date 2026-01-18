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
      name: 'Gmail',
      icon: 'https://www.google.com/gmail/about/static-2.0/images/logo-gmail.png',
      description: 'Connect using Google OAuth. Supports personal and Google Workspace accounts.',
    },
    outlook: {
      name: 'Outlook / Microsoft 365',
      icon: 'https://upload.wikimedia.org/wikipedia/commons/d/df/Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg',
      description: 'Connect using Microsoft OAuth. Supports Outlook.com and Microsoft 365 accounts.',
    },
    generic: {
      name: 'Generic IMAP',
      icon: '',
      description: 'Connect to any IMAP server using traditional credentials.',
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
        Email Provider
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
          <span class="text-sm font-medium text-text-primary">Gmail</span>
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
          <span class="text-sm font-medium text-text-primary">Outlook</span>
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
          <span class="text-sm font-medium text-text-primary">IMAP</span>
        </button>
      </div>

      <!-- Status indicators -->
      <div class="mt-2 flex items-center gap-3 text-xs text-text-muted">
        <Loader2 v-if="isLoadingProviders" :size="14" class="animate-spin" />
        <span v-else-if="!isGmailConfigured && !isOutlookConfigured">
          OAuth providers not configured
        </span>
        <span v-else>{{ providerInfo.description }}</span>
      </div>
    </div>

    <!-- OAuth Provider Info (Gmail/Outlook) -->
    <div v-if="provider !== 'generic'" class="rounded-lg border border-border-subtle bg-bg-surface p-4">
      <div class="flex items-start gap-3">
        <Lock :size="20" class="mt-0.5 flex-shrink-0 text-accent-primary" />
        <div>
          <h4 class="text-sm font-medium text-text-primary">Secure OAuth Authentication</h4>
          <p class="mt-1 text-xs text-text-muted">
            After creating this source, you'll be redirected to {{ provider === 'gmail' ? 'Google' : 'Microsoft' }}
            to authorize access. Your password is never stored - we use secure OAuth tokens.
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
          <span class="text-sm font-medium text-text-primary">Server Settings</span>
          <span v-if="hasServerSettings && !showServerSettings" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
            configured
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
              IMAP Server
            </label>
            <input
              v-model="imapHost"
              type="text"
              placeholder="imap.example.com"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Port & SSL Row -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-text-primary">
                Port
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
                SSL/TLS
              </label>
              <button
                type="button"
                @click="imapUseSsl = !imapUseSsl"
                class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors"
                :class="imapUseSsl
                  ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                  : 'border-border-subtle bg-bg-base text-text-muted'"
              >
                <span>{{ imapUseSsl ? 'Enabled' : 'Disabled' }}</span>
                <Lock :size="14" />
              </button>
            </div>
          </div>

          <!-- Username -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              <User :size="14" class="mr-1 inline" />
              Username
            </label>
            <input
              v-model="imapUsername"
              type="text"
              placeholder="user@example.com"
              autocomplete="username"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Password -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              <Lock :size="14" class="mr-1 inline" />
              Password
            </label>
            <div class="relative">
              <input
                v-model="imapPassword"
                :type="showPassword ? 'text' : 'password'"
                placeholder="Enter password"
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
              Encrypted before storage.
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
          <span class="text-sm font-medium text-text-primary">Email Filters</span>
          <span v-if="hasFilters" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
            configured
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
              Folders
            </label>
            <input
              v-model="folders"
              type="text"
              placeholder="INBOX, Newsletters"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
            <p class="mt-1 text-xs text-text-muted">
              Comma-separated. Leave empty for INBOX only.
            </p>
          </div>

          <!-- From Filter -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              Sender Filter
            </label>
            <input
              v-model="fromFilter"
              type="text"
              placeholder="@newsletter.com"
              class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
            />
          </div>

          <!-- Subject Filter -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-text-primary">
              Subject Filter
            </label>
            <input
              v-model="subjectFilter"
              type="text"
              placeholder="Weekly Report"
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
