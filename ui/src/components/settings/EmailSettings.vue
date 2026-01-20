<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { settingsApi, apiClient } from '@/services/api';
import SettingField from './SettingField.vue';
import { useToast } from '@/composables/useToast';
import { Loader2, Save, RotateCcw, Mail, Send } from 'lucide-vue-next';
import type { SettingValue } from '@/types/entities';

const queryClient = useQueryClient();
const toast = useToast();
const testEmail = ref('');
const testing = ref(false);

// Settings query for email category
const { data: settings, isLoading } = useQuery({
  queryKey: ['settings', 'email'],
  queryFn: () => settingsApi.get('email'),
  staleTime: 30000,
});

// Local form state for editable settings
const localSettings = ref<{
  smtp_host: string;
  smtp_port: number;
  from_address: string;
  from_name: string;
}>({
  smtp_host: 'localhost',
  smtp_port: 587,
  from_address: '',
  from_name: 'Reconly',
});

// Track if form has changes
const hasChanges = ref(false);

// Update local settings when data loads
const updateLocalFromSettings = () => {
  if (settings.value?.email) {
    const e = settings.value.email;
    if (e.smtp_host?.value !== undefined) {
      localSettings.value.smtp_host = String(e.smtp_host.value || 'localhost');
    }
    if (e.smtp_port?.value !== undefined) {
      localSettings.value.smtp_port = Number(e.smtp_port.value) || 587;
    }
    if (e.from_address?.value !== undefined) {
      localSettings.value.from_address = String(e.from_address.value || '');
    }
    if (e.from_name?.value !== undefined) {
      localSettings.value.from_name = String(e.from_name.value || 'Reconly');
    }
    hasChanges.value = false;
  }
};

// Watch for settings changes
watch(settings, () => {
  updateLocalFromSettings();
}, { immediate: true });

// Handle field updates
const handleUpdate = (key: string, value: unknown) => {
  (localSettings.value as any)[key] = value;
  hasChanges.value = true;
};

// Save mutation
const saveMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.update({
      settings: [
        { key: 'email.smtp_host', value: localSettings.value.smtp_host },
        { key: 'email.smtp_port', value: localSettings.value.smtp_port },
        { key: 'email.from_address', value: localSettings.value.from_address },
        { key: 'email.from_name', value: localSettings.value.from_name },
      ],
    });
  },
  onSuccess: () => {
    toast.success('Email settings saved');
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to save settings');
  },
});

// Reset mutation
const resetMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.reset({
      keys: ['email.smtp_host', 'email.smtp_port', 'email.from_address', 'email.from_name'],
    });
  },
  onSuccess: () => {
    toast.success('Email settings reset to defaults');
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to reset settings');
  },
});

// Test email connection
const testConnection = async () => {
  if (!testEmail.value) {
    toast.warning('Please enter a test email address');
    return;
  }

  testing.value = true;
  try {
    await apiClient.post('/settings/test-email', {
      to_email: testEmail.value,
      subject: 'Reconly Test Email',
      body: 'This is a test email from Reconly. If you receive this, your email configuration is working correctly!',
    });
    toast.success(`Test email sent to ${testEmail.value}`);
  } catch (error: any) {
    toast.error(error.response?.data?.detail || 'Failed to send test email');
  } finally {
    testing.value = false;
  }
};

// Get email setting as SettingValue format
const getEmailSetting = (key: string): SettingValue => {
  if (!settings.value?.email?.[key]) {
    return { value: null, source: 'default', editable: true };
  }
  return settings.value.email[key];
};
</script>

<template>
  <div class="space-y-6">
    <!-- Email Settings Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
      <div class="flex items-center gap-3 mb-6">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
          <Mail :size="20" class="text-accent-primary" />
        </div>
        <h2 class="text-lg font-semibold text-text-primary">SMTP Configuration</h2>
      </div>

      <div v-if="isLoading" class="flex items-center justify-center py-12">
        <Loader2 :size="32" class="animate-spin text-accent-primary" />
      </div>

      <div v-else class="space-y-6">
        <!-- Editable Fields Grid -->
        <div class="grid gap-6 md:grid-cols-2">
          <!-- SMTP Host -->
          <SettingField
            setting-key="smtp_host"
            :setting="{ value: localSettings.smtp_host, source: getEmailSetting('smtp_host').source, editable: true }"
            label="SMTP Host"
            type="text"
            description="SMTP server hostname (e.g., smtp.gmail.com)"
            @update="handleUpdate('smtp_host', $event)"
          />

          <!-- SMTP Port -->
          <SettingField
            setting-key="smtp_port"
            :setting="{ value: localSettings.smtp_port, source: getEmailSetting('smtp_port').source, editable: true }"
            label="SMTP Port"
            type="number"
            description="Common: 587 (TLS), 465 (SSL), 25 (unencrypted)"
            @update="handleUpdate('smtp_port', $event)"
          />

          <!-- From Email -->
          <SettingField
            setting-key="from_address"
            :setting="{ value: localSettings.from_address, source: getEmailSetting('from_address').source, editable: true }"
            label="From Email Address"
            type="text"
            description="Sender email address"
            @update="handleUpdate('from_address', $event)"
          />

          <!-- From Name -->
          <SettingField
            setting-key="from_name"
            :setting="{ value: localSettings.from_name, source: getEmailSetting('from_name').source, editable: true }"
            label="From Name"
            type="text"
            description="Sender display name"
            @update="handleUpdate('from_name', $event)"
          />
        </div>

        <!-- Save/Reset Buttons -->
        <div class="flex justify-end gap-3 pt-4 border-t border-border-subtle">
          <button
            type="button"
            :disabled="resetMutation.isPending.value"
            @click="resetMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-secondary hover:bg-bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw :size="16" />
            Reset to Defaults
          </button>
          <button
            type="button"
            :disabled="!hasChanges || saveMutation.isPending.value"
            @click="saveMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="saveMutation.isPending.value" :size="16" class="animate-spin" />
            <Save v-else :size="16" />
            Save Changes
          </button>
        </div>
      </div>
    </div>

    <!-- Test Email Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
      <div class="flex items-center gap-3 mb-6">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-green-500/10">
          <Send :size="20" class="text-green-500" />
        </div>
        <h2 class="text-lg font-semibold text-text-primary">Test Email Connection</h2>
      </div>

      <div class="space-y-4">
        <div>
          <label for="test_email" class="block text-sm font-medium text-text-primary mb-2">
            Test Email Address
          </label>
          <input
            id="test_email"
            v-model="testEmail"
            type="email"
            placeholder="test@example.com"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
          />
        </div>

        <div class="flex items-center gap-4">
          <button
            @click="testConnection"
            :disabled="testing || !testEmail"
            class="inline-flex items-center gap-2 rounded-lg bg-green-600 px-6 py-2.5 font-medium text-white transition-all hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="testing" :size="16" class="animate-spin" />
            <Send v-else :size="16" />
            <span>{{ testing ? 'Sending...' : 'Send Test Email' }}</span>
          </button>
          <p class="text-sm text-text-muted">
            Send a test email to verify your SMTP configuration.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
