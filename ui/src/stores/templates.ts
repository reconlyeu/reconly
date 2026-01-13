/**
 * Pinia store for Templates (Prompt and Report)
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { PromptTemplate, ReportTemplate } from '@/types/entities';

export const useTemplatesStore = defineStore('templates', () => {
  // State
  const promptTemplates = ref<PromptTemplate[]>([]);
  const reportTemplates = ref<ReportTemplate[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const activeTab = ref<'prompt' | 'report'>('prompt');

  // Getters - Prompt Templates
  const systemPromptTemplates = computed(() => {
    return promptTemplates.value.filter((t) => t.is_system);
  });

  const userPromptTemplates = computed(() => {
    return promptTemplates.value.filter((t) => !t.is_system);
  });

  const promptTemplateById = computed(() => {
    return (id: number) => promptTemplates.value.find((t) => t.id === id);
  });

  // Getters - Report Templates
  const systemReportTemplates = computed(() => {
    return reportTemplates.value.filter((t) => t.is_system);
  });

  const userReportTemplates = computed(() => {
    return reportTemplates.value.filter((t) => !t.is_system);
  });

  const reportTemplateById = computed(() => {
    return (id: number) => reportTemplates.value.find((t) => t.id === id);
  });

  // Actions - Prompt Templates
  const setPromptTemplates = (templates: PromptTemplate[]) => {
    promptTemplates.value = templates;
  };

  const addPromptTemplate = (template: PromptTemplate) => {
    promptTemplates.value.push(template);
  };

  const updatePromptTemplate = (id: number, updates: Partial<PromptTemplate>) => {
    const index = promptTemplates.value.findIndex((t) => t.id === id);
    if (index !== -1) {
      promptTemplates.value[index] = { ...promptTemplates.value[index], ...updates };
    }
  };

  const removePromptTemplate = (id: number) => {
    promptTemplates.value = promptTemplates.value.filter((t) => t.id !== id);
  };

  // Actions - Report Templates
  const setReportTemplates = (templates: ReportTemplate[]) => {
    reportTemplates.value = templates;
  };

  const addReportTemplate = (template: ReportTemplate) => {
    reportTemplates.value.push(template);
  };

  const updateReportTemplate = (id: number, updates: Partial<ReportTemplate>) => {
    const index = reportTemplates.value.findIndex((t) => t.id === id);
    if (index !== -1) {
      reportTemplates.value[index] = { ...reportTemplates.value[index], ...updates };
    }
  };

  const removeReportTemplate = (id: number) => {
    reportTemplates.value = reportTemplates.value.filter((t) => t.id !== id);
  };

  // Actions - General
  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  const setError = (value: string | null) => {
    error.value = value;
  };

  const setActiveTab = (tab: 'prompt' | 'report') => {
    activeTab.value = tab;
  };

  return {
    // State
    promptTemplates,
    reportTemplates,
    loading,
    error,
    activeTab,
    // Getters - Prompt
    systemPromptTemplates,
    userPromptTemplates,
    promptTemplateById,
    // Getters - Report
    systemReportTemplates,
    userReportTemplates,
    reportTemplateById,
    // Actions - Prompt
    setPromptTemplates,
    addPromptTemplate,
    updatePromptTemplate,
    removePromptTemplate,
    // Actions - Report
    setReportTemplates,
    addReportTemplate,
    updateReportTemplate,
    removeReportTemplate,
    // Actions - General
    setLoading,
    setError,
    setActiveTab,
  };
});
