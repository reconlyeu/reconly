<script setup lang="ts">
/**
 * Modal for browsing and installing extensions from the catalog.
 * Provides search, filtering, and one-click install functionality.
 */
import { ref, computed, watch } from 'vue';
import {
  X,
  Search,
  RefreshCw,
  Puzzle,
  Filter,
  ShieldCheck,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import { useToast } from '@/composables/useToast';
import {
  useCatalog,
  useInstallExtension,
  useUninstallExtension,
} from '@/composables/useExtensions';
import CatalogExtensionCard from './CatalogExtensionCard.vue';
import type { CatalogEntry, ExtensionType } from '@/types/entities';

interface Props {
  isOpen: boolean;
}

interface Emits {
  (e: 'close'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const toast = useToast();

// Catalog query
const { data: catalog, isLoading, isError, error, refetch } = useCatalog();

// Search and filter state
const searchQuery = ref('');
const typeFilter = ref<ExtensionType | ''>('');
const verifiedOnly = ref(false);

// Track which extension is being installed/uninstalled
const installingPackage = ref<string | null>(null);
const uninstallingPackage = ref<string | null>(null);

// Install mutation
const installMutation = useInstallExtension({
  onSuccess: (data) => {
    const name = installingPackage.value?.replace('reconly-ext-', '') || 'Extension';
    toast.success(
      strings.settings.extensions.catalog.installSuccess.replace('{name}', name)
    );
    toast.info(strings.settings.extensions.catalog.restartRequired);
    installingPackage.value = null;
  },
  onError: (err: any) => {
    // Show the detailed error from API (includes pip command for dev mode)
    const errorDetail = err?.response?.data?.detail || err?.message || 'Installation failed';
    toast.error(errorDetail, { timeout: 10000 });
    installingPackage.value = null;
  },
});

// Uninstall mutation
const uninstallMutation = useUninstallExtension({
  onSuccess: (data) => {
    const name = uninstallingPackage.value?.replace('reconly-ext-', '') || 'Extension';
    toast.success(
      strings.settings.extensions.catalog.uninstallSuccess.replace('{name}', name)
    );
    toast.info(strings.settings.extensions.catalog.restartRequired);
    uninstallingPackage.value = null;
  },
  onError: (err) => {
    const name = uninstallingPackage.value?.replace('reconly-ext-', '') || 'Extension';
    toast.error(
      strings.settings.extensions.catalog.uninstallFailed.replace('{name}', name)
    );
    uninstallingPackage.value = null;
  },
});

// Filtered catalog based on search and filters
const filteredCatalog = computed(() => {
  if (!catalog.value) return [];

  let results = catalog.value;

  // Filter by type
  if (typeFilter.value) {
    results = results.filter((e) => e.type === typeFilter.value);
  }

  // Filter by verified
  if (verifiedOnly.value) {
    results = results.filter((e) => e.verified);
  }

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    results = results.filter(
      (e) =>
        e.name.toLowerCase().includes(query) ||
        e.description.toLowerCase().includes(query) ||
        e.package.toLowerCase().includes(query)
    );
  }

  return results;
});

// Handle install
// For GitHub extensions, use github_url; for PyPI extensions, use package name
const handleInstall = (entry: CatalogEntry) => {
  installingPackage.value = entry.package;
  if (entry.install_source === 'github' && entry.github_url) {
    installMutation.mutate({ githubUrl: entry.github_url });
  } else {
    installMutation.mutate({ packageName: entry.package });
  }
};

// Handle uninstall
const handleUninstall = (entry: CatalogEntry) => {
  uninstallingPackage.value = entry.package;
  // Extract name from package (remove 'reconly-ext-' prefix)
  const name = entry.package.replace('reconly-ext-', '');
  uninstallMutation.mutate({ type: entry.type, name });
};

// Close modal
const handleClose = () => {
  emit('close');
};

// Reset filters when modal opens
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    searchQuery.value = '';
    typeFilter.value = '';
    verifiedOnly.value = false;
  }
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
        @click.self="handleClose"
      >
        <Transition
          enter-active-class="duration-300 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="duration-200 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="isOpen"
            class="relative w-full max-w-4xl max-h-[85vh] overflow-hidden rounded-2xl border border-border-subtle bg-bg-surface shadow-2xl flex flex-col"
          >
            <!-- Header -->
            <div class="flex items-center justify-between border-b border-border-subtle px-6 py-4">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
                  <Puzzle :size="20" class="text-accent-primary" />
                </div>
                <div>
                  <h2 class="text-lg font-semibold text-text-primary">
                    {{ strings.settings.extensions.catalog.title }}
                  </h2>
                  <p class="text-sm text-text-muted">
                    {{ strings.settings.extensions.catalog.description }}
                  </p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  @click="() => refetch()"
                  :disabled="isLoading"
                  class="p-2 rounded-lg bg-bg-elevated hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
                  :title="'Refresh catalog'"
                >
                  <RefreshCw :size="18" :class="{ 'animate-spin': isLoading }" />
                </button>
                <button
                  @click="handleClose"
                  class="p-2 rounded-lg bg-bg-elevated hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
                >
                  <X :size="18" />
                </button>
              </div>
            </div>

            <!-- Search and Filters -->
            <div class="flex flex-wrap items-center gap-3 border-b border-border-subtle px-6 py-3">
              <!-- Search input -->
              <div class="relative flex-1 min-w-[200px]">
                <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  v-model="searchQuery"
                  type="text"
                  :placeholder="strings.settings.extensions.catalog.search"
                  class="w-full rounded-lg bg-bg-elevated border border-border-subtle pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                />
              </div>

              <!-- Type filter -->
              <div class="flex items-center gap-2">
                <Filter :size="16" class="text-text-muted" />
                <select
                  v-model="typeFilter"
                  class="rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                >
                  <option value="">{{ strings.settings.extensions.catalog.allTypes }}</option>
                  <option value="exporter">Exporter</option>
                  <option value="fetcher">Fetcher</option>
                  <option value="provider">Provider</option>
                </select>
              </div>

              <!-- Verified only toggle -->
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="verifiedOnly"
                  type="checkbox"
                  class="h-4 w-4 rounded border-border-subtle bg-bg-elevated text-accent-primary focus:ring-accent-primary focus:ring-offset-0"
                />
                <span class="flex items-center gap-1 text-sm text-text-secondary">
                  <ShieldCheck :size="14" class="text-green-400" />
                  {{ strings.settings.extensions.catalog.verifiedOnly }}
                </span>
              </label>
            </div>

            <!-- Content -->
            <div class="flex-1 overflow-y-auto p-6">
              <!-- Loading state -->
              <div v-if="isLoading" class="flex items-center justify-center py-12">
                <div class="flex items-center gap-3 text-text-muted">
                  <RefreshCw :size="20" class="animate-spin" />
                  <span>{{ strings.settings.extensions.catalog.loading }}</span>
                </div>
              </div>

              <!-- Error state -->
              <div v-else-if="isError" class="rounded-lg bg-red-500/10 border border-red-500/20 p-4">
                <p class="text-sm text-red-400">
                  {{ strings.settings.extensions.catalog.error }}: {{ error?.message || 'Unknown error' }}
                </p>
              </div>

              <!-- Empty state -->
              <div
                v-else-if="filteredCatalog.length === 0"
                class="flex flex-col items-center justify-center py-12 text-center"
              >
                <div class="flex h-16 w-16 items-center justify-center rounded-full bg-bg-elevated">
                  <Puzzle :size="32" class="text-text-muted" />
                </div>
                <h3 class="mt-4 text-lg font-semibold text-text-primary">
                  {{ strings.settings.extensions.catalog.noResults }}
                </h3>
                <p class="mt-2 text-sm text-text-muted">
                  {{ strings.settings.extensions.catalog.noResultsDescription }}
                </p>
              </div>

              <!-- Catalog grid -->
              <div v-else class="grid gap-4 sm:grid-cols-2">
                <CatalogExtensionCard
                  v-for="entry in filteredCatalog"
                  :key="entry.package"
                  :entry="entry"
                  :is-installing="installingPackage === entry.package"
                  :is-uninstalling="uninstallingPackage === entry.package"
                  @install="handleInstall"
                  @uninstall="handleUninstall"
                />
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
