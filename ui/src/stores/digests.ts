/**
 * Pinia store for Digests
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Digest, Tag } from '@/types/entities';

export interface DigestFilters {
  feedId?: number | null;
  sourceId?: number | null;
  tags?: string | null;  // Comma-separated tag names
  search?: string;
}

export const useDigestsStore = defineStore('digests', () => {
  // State
  const digests = ref<Digest[]>([]);
  const tags = ref<Tag[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const filters = ref<DigestFilters>({});
  const selectedIds = ref<Set<number>>(new Set());
  const pagination = ref({
    page: 1,
    perPage: 20,
    total: 0,
    totalPages: 0,
  });

  // Getters
  const digestsCount = computed(() => pagination.value.total);

  const hasFilters = computed(() => {
    return !!(filters.value.feedId || filters.value.sourceId || filters.value.tags || filters.value.search);
  });

  const selectedDigests = computed(() => {
    return digests.value.filter((d) => selectedIds.value.has(d.id));
  });

  const hasSelection = computed(() => selectedIds.value.size > 0);

  const allSelected = computed(() => {
    return digests.value.length > 0 && digests.value.every((d) => selectedIds.value.has(d.id));
  });

  // Actions
  const setDigests = (newDigests: Digest[]) => {
    digests.value = newDigests;
  };

  const addDigest = (digest: Digest) => {
    digests.value.unshift(digest);
  };

  const removeDigest = (id: number) => {
    digests.value = digests.value.filter((d) => d.id !== id);
    selectedIds.value.delete(id);
  };

  const setTags = (newTags: Tag[]) => {
    tags.value = newTags;
  };

  const setFilters = (newFilters: DigestFilters) => {
    filters.value = newFilters;
    // Reset pagination when filters change
    pagination.value.page = 1;
  };

  const clearFilters = () => {
    filters.value = {};
    pagination.value.page = 1;
  };

  const setPagination = (data: Partial<typeof pagination.value>) => {
    pagination.value = { ...pagination.value, ...data };
  };

  const setPage = (page: number) => {
    pagination.value.page = page;
  };

  // Selection
  const toggleSelection = (id: number) => {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id);
    } else {
      selectedIds.value.add(id);
    }
  };

  const selectAll = () => {
    digests.value.forEach((d) => selectedIds.value.add(d.id));
  };

  const clearSelection = () => {
    selectedIds.value.clear();
  };

  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  const setError = (value: string | null) => {
    error.value = value;
  };

  return {
    // State
    digests,
    tags,
    loading,
    error,
    filters,
    selectedIds,
    pagination,
    // Getters
    digestsCount,
    hasFilters,
    selectedDigests,
    hasSelection,
    allSelected,
    // Actions
    setDigests,
    addDigest,
    removeDigest,
    setTags,
    setFilters,
    clearFilters,
    setPagination,
    setPage,
    toggleSelection,
    selectAll,
    clearSelection,
    setLoading,
    setError,
  };
});
