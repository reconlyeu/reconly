<script setup lang="ts">
/**
 * Selector component for choosing an export format.
 * Uses BaseList for consistent loading/error/empty states.
 * Renders ExporterCard for each available exporter.
 */
import { FileDown } from 'lucide-vue-next';
import BaseList from '@/components/common/BaseList.vue';
import ExporterCard from './ExporterCard.vue';
import { useExportersList, useToggleExporter } from '@/composables/useExporters';
import { useToast } from '@/composables/useToast';
import type { Exporter } from '@/types/entities';

interface Props {
  /** Currently selected exporter name */
  modelValue: string;
}

interface Emits {
  (e: 'update:modelValue', value: string): void;
}

defineProps<Props>();
const emit = defineEmits<Emits>();

const toast = useToast();

// Fetch exporters using the composable
const { data: exporters, isLoading, isError, error, refetch } = useExportersList();

// Toggle mutation
const toggleMutation = useToggleExporter({
  onSuccess: (data) => {
    toast.success(`${data.name} ${data.enabled ? 'enabled' : 'disabled'}`);
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to toggle exporter');
  },
});

const handleSelect = (exporterName: string) => {
  emit('update:modelValue', exporterName);
};

const handleToggle = (exporterName: string, enabled: boolean) => {
  toggleMutation.mutate({ name: exporterName, enabled });
};
</script>

<template>
  <BaseList
    :items="exporters || []"
    :is-loading="isLoading"
    :is-error="isError"
    :error="error"
    entity-name="exporter"
    :grid-cols="2"
    :skeleton-count="4"
    skeleton-height="h-48"
    empty-title="No exporters available"
    empty-message="Export formats will appear here once they are registered."
    :empty-icon="FileDown"
    @retry="refetch"
  >
    <template #default="{ items }">
      <ExporterCard
        v-for="exporter in (items as Exporter[])"
        :key="exporter.name"
        :exporter="exporter"
        :selected="modelValue === exporter.name"
        :is-toggling="toggleMutation.isPending.value"
        @select="handleSelect"
        @toggle="handleToggle"
      />
    </template>

    <template #empty-action>
      <p class="text-sm text-text-muted">
        Check your installation or contact support if exporters are missing.
      </p>
    </template>
  </BaseList>
</template>
