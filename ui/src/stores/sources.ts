/**
 * Pinia store for Sources
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Source, SourceType } from '@/types/entities';

export const useSourcesStore = defineStore('sources', () => {
  // State
  const sources = ref<Source[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const selectedType = ref<SourceType | 'all'>('all');

  // Getters
  const filteredSources = computed(() => {
    if (selectedType.value === 'all') {
      return sources.value;
    }
    return sources.value.filter((s) => s.type === selectedType.value);
  });

  const sourcesByType = computed(() => {
    return {
      rss: sources.value.filter((s) => s.type === 'rss'),
      youtube: sources.value.filter((s) => s.type === 'youtube'),
      website: sources.value.filter((s) => s.type === 'website'),
      blog: sources.value.filter((s) => s.type === 'blog'),
    };
  });

  const enabledSources = computed(() => {
    return sources.value.filter((s) => s.enabled);
  });

  const sourcesCount = computed(() => sources.value.length);

  // Actions
  const setSources = (newSources: Source[]) => {
    sources.value = newSources;
  };

  const addSource = (source: Source) => {
    sources.value.push(source);
  };

  const updateSource = (id: number, updates: Partial<Source>) => {
    const index = sources.value.findIndex((s) => s.id === id);
    if (index !== -1) {
      sources.value[index] = { ...sources.value[index], ...updates };
    }
  };

  const removeSource = (id: number) => {
    sources.value = sources.value.filter((s) => s.id !== id);
  };

  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  const setError = (value: string | null) => {
    error.value = value;
  };

  const setSelectedType = (type: SourceType | 'all') => {
    selectedType.value = type;
  };

  return {
    // State
    sources,
    loading,
    error,
    selectedType,
    // Getters
    filteredSources,
    sourcesByType,
    enabledSources,
    sourcesCount,
    // Actions
    setSources,
    addSource,
    updateSource,
    removeSource,
    setLoading,
    setError,
    setSelectedType,
  };
});
