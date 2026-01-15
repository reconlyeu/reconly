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
import { Mail, Lock, Server, Folder, User, Eye, EyeOff, Loader2 } from 'lucide-vue-next';

interface Props {
  /** Whether the form is in loading/saving state */
  isLoading?: boolean;
}

defineProps<Props>();

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
</script>

<template>
  <div class="space-y-6">
    <!-- Provider Selection -->
    <div>
      <label class="mb-2 block text-sm font-medium text-text-primary">
        Email Provider
      </label>
      <p class="mb-3 text-xs text-text-muted">
        Select your email provider for authentication
      </p>

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <!-- Gmail Option -->
        <button
          type="button"
          @click="provider = 'gmail'"
          class="relative flex flex-col items-center rounded-lg border p-4 transition-all"
          :class="[
            provider === 'gmail'
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover',
            !isGmailConfigured && 'opacity-50'
          ]"
          :disabled="!isGmailConfigured"
        >
          <Mail :size="24" class="mb-2 text-red-500" />
          <span class="text-sm font-medium text-text-primary">Gmail</span>
          <span v-if="!isGmailConfigured && !isLoadingProviders" class="mt-1 text-xs text-text-muted">
            Not configured
          </span>
          <div v-if="provider === 'gmail'" class="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-primary" />
        </button>

        <!-- Outlook Option -->
        <button
          type="button"
          @click="provider = 'outlook'"
          class="relative flex flex-col items-center rounded-lg border p-4 transition-all"
          :class="[
            provider === 'outlook'
              ? 'border-accent-primary bg-accent-primary/10'
              : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover',
            !isOutlookConfigured && 'opacity-50'
          ]"
          :disabled="!isOutlookConfigured"
        >
          <Mail :size="24" class="mb-2 text-blue-500" />
          <span class="text-sm font-medium text-text-primary">Outlook</span>
          <span v-if="!isOutlookConfigured && !isLoadingProviders" class="mt-1 text-xs text-text-muted">
            Not configured
          </span>
          <div v-if="provider === 'outlook'" class="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-primary" />
        </button>

        <!-- Generic IMAP Option -->
        <button
          type="button"
          @click="provider = 'generic'"
          class="relative flex flex-col items-center rounded-lg border p-4 transition-all"
          :class="provider === 'generic'
            ? 'border-accent-primary bg-accent-primary/10'
            : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover'"
        >
          <Server :size="24" class="mb-2 text-text-muted" />
          <span class="text-sm font-medium text-text-primary">Generic IMAP</span>
          <div v-if="provider === 'generic'" class="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-primary" />
        </button>
      </div>

      <!-- Loading indicator for providers -->
      <div v-if="isLoadingProviders" class="mt-2 flex items-center gap-2 text-xs text-text-muted">
        <Loader2 :size="14" class="animate-spin" />
        Checking OAuth configuration...
      </div>
    </div>

    <!-- Provider Description -->
    <p class="text-sm text-text-muted">
      {{ providerInfo.description }}
    </p>

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

    <!-- Generic IMAP Fields -->
    <div v-if="provider === 'generic'" class="space-y-4">
      <!-- IMAP Server -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          <Server :size="14" class="mr-1.5 inline" />
          IMAP Server
        </label>
        <input
          v-model="imapHost"
          type="text"
          placeholder="imap.example.com"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
      </div>

      <!-- Port & SSL Row -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            Port
          </label>
          <input
            v-model.number="imapPort"
            type="number"
            min="1"
            max="65535"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
          />
        </div>
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            Use SSL/TLS
          </label>
          <button
            type="button"
            @click="imapUseSsl = !imapUseSsl"
            class="flex w-full items-center justify-between rounded-lg border px-4 py-3 transition-colors"
            :class="imapUseSsl
              ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
              : 'border-border-subtle bg-bg-surface text-text-muted'"
          >
            <span class="text-sm">{{ imapUseSsl ? 'Enabled' : 'Disabled' }}</span>
            <Lock :size="16" />
          </button>
        </div>
      </div>

      <!-- Username -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          <User :size="14" class="mr-1.5 inline" />
          Username
        </label>
        <input
          v-model="imapUsername"
          type="text"
          placeholder="user@example.com"
          autocomplete="username"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
      </div>

      <!-- Password -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          <Lock :size="14" class="mr-1.5 inline" />
          Password
        </label>
        <div class="relative">
          <input
            v-model="imapPassword"
            :type="showPassword ? 'text' : 'password'"
            placeholder="Enter password"
            autocomplete="current-password"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 pr-12 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
          />
          <button
            type="button"
            @click="showPassword = !showPassword"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted transition-colors hover:text-text-primary"
          >
            <Eye v-if="!showPassword" :size="18" />
            <EyeOff v-else :size="18" />
          </button>
        </div>
        <p class="mt-1 text-xs text-text-muted">
          Password is encrypted before storage and never exposed in API responses.
        </p>
      </div>
    </div>

    <!-- Shared Email Filtering Options -->
    <div class="space-y-4 border-t border-border-subtle pt-4">
      <h4 class="text-sm font-medium text-text-primary">Email Filtering Options</h4>

      <!-- Folders -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          <Folder :size="14" class="mr-1.5 inline" />
          Folders
        </label>
        <input
          v-model="folders"
          type="text"
          placeholder="INBOX, Newsletters (comma-separated)"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
        <p class="mt-1 text-xs text-text-muted">
          IMAP folders to fetch emails from. Leave empty for INBOX only.
        </p>
      </div>

      <!-- From Filter -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          Sender Filter (optional)
        </label>
        <input
          v-model="fromFilter"
          type="text"
          placeholder="@newsletter.com"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
        <p class="mt-1 text-xs text-text-muted">
          Only fetch emails from senders matching this pattern.
        </p>
      </div>

      <!-- Subject Filter -->
      <div>
        <label class="mb-2 block text-sm font-medium text-text-primary">
          Subject Filter (optional)
        </label>
        <input
          v-model="subjectFilter"
          type="text"
          placeholder="Weekly Report"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
        <p class="mt-1 text-xs text-text-muted">
          Only fetch emails with subjects matching this pattern.
        </p>
      </div>
    </div>
  </div>
</template>
