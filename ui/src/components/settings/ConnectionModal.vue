<script setup lang="ts">
/**
 * Modal for creating and editing email IMAP connections.
 * Features provider auto-fill, inline test functionality, and validation.
 */
import { ref, computed, watch } from 'vue';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { X, Mail, Loader2, CheckCircle, XCircle, Eye, EyeOff } from 'lucide-vue-next';
import { Icon } from '@iconify/vue';
import { connectionsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import { strings } from '@/i18n/en';
import type { Connection, ConnectionProvider, ConnectionCreate, ConnectionUpdate, EmailIMAPConfig } from '@/types/entities';

interface Props {
  isOpen: boolean;
  connection?: Connection | null; // null = create mode, Connection = edit mode
}

interface Emits {
  (e: 'close'): void;
  (e: 'saved', connection: Connection): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const toast = useToast();
const queryClient = useQueryClient();

// Form state
const name = ref('');
const provider = ref<ConnectionProvider>('generic');
const host = ref('');
const port = ref(993);
const username = ref('');
const password = ref('');
const useSsl = ref(true);

// UI state
const showPassword = ref(false);
const testResult = ref<{ success: boolean; message: string } | null>(null);

// Provider configurations for auto-fill
const providerConfigs: Record<ConnectionProvider, { host: string; port: number; readonly: boolean }> = {
  gmail: { host: 'imap.gmail.com', port: 993, readonly: true },
  outlook: { host: 'outlook.office365.com', port: 993, readonly: true },
  generic: { host: '', port: 993, readonly: false },
};

const providerOptions: { value: ConnectionProvider; label: string; icon: string }[] = [
  { value: 'gmail', label: strings.settings.email.connections.providers.gmail, icon: 'mdi:gmail' },
  { value: 'outlook', label: strings.settings.email.connections.providers.outlook, icon: 'mdi:microsoft-outlook' },
  { value: 'generic', label: strings.settings.email.connections.providers.generic, icon: 'mdi:email-outline' },
];

// Computed
const isEditMode = computed(() => !!props.connection);
const modalTitle = computed(() =>
  isEditMode.value
    ? strings.settings.email.connections.editTitle
    : strings.settings.email.connections.createTitle
);
const isHostReadonly = computed(() => providerConfigs[provider.value].readonly);

const providerHint = computed(() => {
  const hints = strings.settings.email.connections.providerHints;
  return hints[provider.value as keyof typeof hints] || '';
});

const canSave = computed(() => {
  return name.value.trim() !== '' &&
         username.value.trim() !== '' &&
         (isEditMode.value || password.value.trim() !== '') &&
         host.value.trim() !== '';
});

// Watch provider changes to auto-fill host/port
watch(provider, (newProvider) => {
  const config = providerConfigs[newProvider];
  host.value = config.host;
  port.value = config.port;
  testResult.value = null;
});

// Reset form when modal opens/closes
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    resetForm();
    if (props.connection) {
      populateFromConnection(props.connection);
    }
  } else {
    // Clean up when closing
    testResult.value = null;
    showPassword.value = false;
  }
});

function resetForm() {
  name.value = '';
  provider.value = 'generic';
  host.value = '';
  port.value = 993;
  username.value = '';
  password.value = '';
  useSsl.value = true;
  testResult.value = null;
  showPassword.value = false;
}

function populateFromConnection(conn: Connection) {
  name.value = conn.name;
  provider.value = conn.provider || 'generic';
  // Note: We don't have access to the decrypted config,
  // so we auto-fill based on provider for edit mode
  const config = providerConfigs[provider.value];
  host.value = config.host || '';
  port.value = config.port;
  useSsl.value = true;
  // Username and password are not available from the connection response
  // User must re-enter them if they want to update credentials
  username.value = '';
  password.value = '';
}

// Create mutation
const createMutation = useMutation({
  mutationFn: (data: ConnectionCreate) => connectionsApi.create(data),
  onSuccess: (newConnection) => {
    toast.success(strings.settings.email.connections.createSuccess);
    queryClient.invalidateQueries({ queryKey: ['connections'] });
    emit('saved', newConnection);
    emit('close');
  },
  onError: (error: any) => {
    toast.error(error.detail || strings.settings.email.connections.createFailed);
  },
});

// Update mutation
const updateMutation = useMutation({
  mutationFn: ({ id, data }: { id: number; data: ConnectionUpdate }) =>
    connectionsApi.update(id, data),
  onSuccess: (updatedConnection) => {
    toast.success(strings.settings.email.connections.updateSuccess);
    queryClient.invalidateQueries({ queryKey: ['connections'] });
    emit('saved', updatedConnection);
    emit('close');
  },
  onError: (error: any) => {
    toast.error(error.detail || strings.settings.email.connections.updateFailed);
  },
});

// Test connection (for existing connections only, test after save)
const testMutation = useMutation({
  mutationFn: (id: number) => connectionsApi.test(id),
  onSuccess: (result) => {
    testResult.value = {
      success: result.success,
      message: result.message,
    };
    if (result.success) {
      toast.success(strings.settings.email.connections.testSuccess);
    } else {
      toast.error(result.message || strings.settings.email.connections.testFailed);
    }
  },
  onError: (error: any) => {
    testResult.value = {
      success: false,
      message: error.detail || strings.settings.email.connections.testFailed,
    };
    toast.error(error.detail || strings.settings.email.connections.testFailed);
  },
});

const isSaving = computed(() => createMutation.isPending.value || updateMutation.isPending.value);

async function handleSave() {
  if (!canSave.value) return;

  const config: EmailIMAPConfig = {
    host: host.value,
    port: port.value,
    username: username.value,
    password: password.value,
    use_ssl: useSsl.value,
  };

  if (isEditMode.value && props.connection) {
    // Update mode - only include fields that have values
    const updateData: ConnectionUpdate = {
      name: name.value,
      provider: provider.value,
    };
    // Only include config if password is provided (user wants to update credentials)
    if (password.value.trim() !== '') {
      updateData.config = config;
    }
    updateMutation.mutate({ id: props.connection.id, data: updateData });
  } else {
    // Create mode
    const createData: ConnectionCreate = {
      name: name.value,
      type: 'email_imap',
      provider: provider.value,
      config,
    };
    createMutation.mutate(createData);
  }
}

function handleTest(): void {
  if (isEditMode.value && props.connection) {
    testMutation.mutate(props.connection.id);
  } else {
    toast.info('Save the connection first to test it');
  }
}

function handleClose() {
  emit('close');
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="handleClose"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/90 backdrop-blur-md" />

        <!-- Modal -->
        <div
          class="relative w-full max-w-lg overflow-hidden rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-base shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orbs -->
          <div class="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-accent-primary/10 blur-3xl" />

          <!-- Header -->
          <div class="border-b border-border-subtle bg-bg-elevated/95 px-6 py-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
                  <Mail :size="20" class="text-accent-primary" />
                </div>
                <h2 class="text-lg font-semibold text-text-primary">{{ modalTitle }}</h2>
              </div>
              <button
                type="button"
                class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                @click="handleClose"
              >
                <X :size="20" />
              </button>
            </div>
          </div>

          <!-- Content -->
          <form @submit.prevent="handleSave" class="relative space-y-5 p-6">
            <!-- Connection Name -->
            <div>
              <label for="conn-name" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.settings.email.connections.fields.name }}
              </label>
              <input
                id="conn-name"
                v-model="name"
                type="text"
                :placeholder="strings.settings.email.connections.fields.namePlaceholder"
                class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
              />
            </div>

            <!-- Provider Selection -->
            <div>
              <label for="conn-provider" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.settings.email.connections.fields.provider }}
              </label>
              <div class="grid grid-cols-3 gap-3">
                <button
                  v-for="opt in providerOptions"
                  :key="opt.value"
                  type="button"
                  class="flex flex-col items-center gap-2 rounded-lg border p-3 transition-all"
                  :class="[
                    provider === opt.value
                      ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                      : 'border-border-subtle bg-bg-surface text-text-muted hover:border-border-default hover:bg-bg-hover'
                  ]"
                  @click="provider = opt.value"
                >
                  <Icon :icon="opt.icon" :width="24" :height="24" />
                  <span class="text-xs font-medium">{{ opt.label }}</span>
                </button>
              </div>
              <p v-if="providerHint" class="mt-2 text-xs text-text-muted">
                {{ providerHint }}
              </p>
            </div>

            <!-- Host & Port (side by side) -->
            <div class="grid grid-cols-3 gap-4">
              <div class="col-span-2">
                <label for="conn-host" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.settings.email.connections.fields.host }}
                </label>
                <input
                  id="conn-host"
                  v-model="host"
                  type="text"
                  :placeholder="strings.settings.email.connections.fields.hostPlaceholder"
                  :readonly="isHostReadonly"
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
                  :class="{ 'bg-bg-hover cursor-not-allowed': isHostReadonly }"
                />
              </div>
              <div>
                <label for="conn-port" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.settings.email.connections.fields.port }}
                </label>
                <input
                  id="conn-port"
                  v-model.number="port"
                  type="number"
                  :readonly="isHostReadonly"
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
                  :class="{ 'bg-bg-hover cursor-not-allowed': isHostReadonly }"
                />
              </div>
            </div>

            <!-- Username -->
            <div>
              <label for="conn-username" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.settings.email.connections.fields.username }}
              </label>
              <input
                id="conn-username"
                v-model="username"
                type="email"
                :placeholder="strings.settings.email.connections.fields.usernamePlaceholder"
                class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
              />
            </div>

            <!-- Password -->
            <div>
              <label for="conn-password" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.settings.email.connections.fields.password }}
                <span v-if="isEditMode" class="text-text-muted font-normal">({{ strings.common.optional }})</span>
              </label>
              <div class="relative">
                <input
                  id="conn-password"
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  :placeholder="strings.settings.email.connections.fields.passwordPlaceholder"
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 pr-10 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                  @click="showPassword = !showPassword"
                >
                  <EyeOff v-if="showPassword" :size="18" />
                  <Eye v-else :size="18" />
                </button>
              </div>
            </div>

            <!-- Use SSL -->
            <div class="flex items-center gap-3">
              <input
                id="conn-ssl"
                v-model="useSsl"
                type="checkbox"
                class="h-4 w-4 rounded border-border-subtle bg-bg-surface text-accent-primary focus:ring-accent-primary focus:ring-offset-bg-base"
              />
              <label for="conn-ssl" class="text-sm text-text-primary">
                {{ strings.settings.email.connections.fields.useSsl }}
              </label>
            </div>

            <!-- Test Connection Button (only for edit mode) -->
            <div v-if="isEditMode" class="pt-2">
              <button
                type="button"
                :disabled="testMutation.isPending.value"
                class="flex items-center gap-2 rounded-lg bg-bg-surface px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-bg-hover disabled:opacity-50"
                @click="handleTest"
              >
                <Loader2 v-if="testMutation.isPending.value" :size="16" class="animate-spin" />
                <CheckCircle v-else-if="testResult?.success" :size="16" class="text-green-400" />
                <XCircle v-else-if="testResult && !testResult.success" :size="16" class="text-red-400" />
                <Mail v-else :size="16" />
                {{ testMutation.isPending.value ? strings.settings.email.connections.testing : strings.settings.email.connections.testConnection }}
              </button>
              <!-- Test result message -->
              <div
                v-if="testResult"
                class="mt-2 flex items-center gap-2 text-sm"
                :class="testResult.success ? 'text-green-400' : 'text-red-400'"
              >
                <CheckCircle v-if="testResult.success" :size="14" />
                <XCircle v-else :size="14" />
                {{ testResult.message }}
              </div>
            </div>
          </form>

          <!-- Footer -->
          <div class="flex justify-end gap-3 border-t border-border-subtle bg-bg-elevated/95 px-6 py-4">
            <button
              type="button"
              class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-bg-hover"
              @click="handleClose"
            >
              {{ strings.common.cancel }}
            </button>
            <button
              type="button"
              :disabled="!canSave || isSaving"
              class="flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              @click="handleSave"
            >
              <Loader2 v-if="isSaving" :size="16" class="animate-spin" />
              {{ isSaving ? strings.settings.email.connections.saving : strings.common.save }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.98) translateY(20px);
  opacity: 0;
}
</style>
