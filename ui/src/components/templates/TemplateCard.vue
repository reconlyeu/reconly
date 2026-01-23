<script setup lang="ts">
import { computed } from 'vue';
import { Shield, Edit, Trash2, FileText, Languages, Code, Download, User } from 'lucide-vue-next';
import type { TemplateOrigin } from '@/types/entities';
import BaseCard from '@/components/common/BaseCard.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import { strings } from '@/i18n/en';

interface Props {
  template: {
    id: number;
    name: string;
    description?: string;
    origin?: TemplateOrigin;
    imported_from_bundle?: string | null;
    is_system: boolean; // backwards compatibility
    is_active: boolean;
    language?: string;
    target_length?: number;
    format?: string;
  };
  type: 'prompt' | 'report';
}

interface Emits {
  (e: 'toggle', templateId: number, enabled: boolean): void;
  (e: 'edit', template: any): void;
  (e: 'delete', templateId: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const typeConfig = computed(() => {
  if (props.type === 'prompt') {
    return {
      icon: Languages,
      label: strings.templates.types.prompt,
      color: 'text-purple-400',
      bgColor: 'bg-purple-400/10',
      glow: 'purple' as const,
    };
  }
  return {
    icon: Code,
    label: strings.templates.types.report,
    color: 'text-orange-400',
    bgColor: 'bg-orange-400/10',
    glow: 'orange' as const,
  };
});

const badgeConfig = computed(() => {
  // Use origin field if available, fall back to is_system for backwards compatibility
  const origin = props.template.origin || (props.template.is_system ? 'builtin' : 'user');

  if (origin === 'builtin') {
    return {
      label: strings.templates.origin.builtin,
      color: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      icon: Shield,
    };
  }
  if (origin === 'imported') {
    return {
      label: strings.templates.origin.imported,
      color: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      icon: Download,
    };
  }
  // 'user' origin
  return {
    label: strings.templates.origin.custom,
    color: 'bg-green-500/10 text-green-400 border-green-500/20',
    icon: User,
  };
});

const metaText = computed(() => {
  if (props.type === 'prompt') {
    const parts = [];
    if (props.template.language) parts.push(props.template.language);
    if (props.template.target_length) parts.push(strings.templates.meta.words.replace('{count}', String(props.template.target_length)));
    return parts.join(' · ') || strings.templates.meta.noSettings;
  } else {
    return props.template.format || strings.templates.meta.noFormat;
  }
});

const handleToggle = (value: boolean) => {
  emit('toggle', props.template.id, value);
};

const handleEdit = () => {
  emit('edit', props.template);
};

const handleDelete = () => {
  emit('delete', props.template.id);
};
</script>

<template>
  <BaseCard :glow-color="typeConfig.glow">
    <template #header>
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <!-- Type Icon -->
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110"
            :class="typeConfig.bgColor"
          >
            <component :is="typeConfig.icon" :class="typeConfig.color" :size="22" :stroke-width="2" />
          </div>

          <!-- Type Label + Built-in/Custom Badge -->
          <div>
            <div class="text-xs font-medium uppercase tracking-wider text-text-muted">
              {{ typeConfig.label }}
            </div>
            <div
              class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium"
              :class="badgeConfig.color"
            >
              <component :is="badgeConfig.icon" :size="12" :stroke-width="2" />
              {{ badgeConfig.label }}
            </div>
          </div>
        </div>

        <!-- Status Badge -->
        <div
          class="rounded-full px-3 py-1 text-xs font-medium transition-colors duration-300"
          :class="
            template.is_active
              ? 'bg-status-success/10 text-status-success'
              : 'bg-text-muted/10 text-text-muted'
          "
        >
          {{ template.is_active ? strings.templates.status.active : strings.templates.status.inactive }}
        </div>
      </div>
    </template>

    <!-- Template Name -->
    <h3 class="mb-2 text-lg font-semibold text-text-primary transition-colors duration-300 group-hover:text-accent-primary">
      {{ template.name }}
    </h3>

    <!-- Description -->
    <p v-if="template.description" class="mb-2 text-sm text-text-muted line-clamp-2">
      {{ template.description }}
    </p>

    <!-- Metadata -->
    <div class="flex items-center gap-2 text-sm">
      <span class="text-text-secondary">{{ metaText }}</span>
    </div>

    <template #footer>
      <div class="flex items-center justify-between">
        <!-- Toggle Switch -->
        <ToggleSwitch
          :model-value="template.is_active"
          @update:model-value="handleToggle"
          :label="template.is_active ? strings.templates.actions.disableTemplate : strings.templates.actions.enableTemplate"
        />

        <!-- Edit & Delete Buttons -->
        <div class="flex gap-2">
          <button
            @click="handleEdit"
            class="rounded-lg p-2 text-text-muted transition-all duration-300 hover:bg-bg-hover hover:text-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.templates.actions.editTemplate"
          >
            <Edit :size="18" :stroke-width="2" />
          </button>
          <button
            @click="handleDelete"
            class="rounded-lg p-2 text-text-muted transition-all duration-300 hover:bg-status-failed/10 hover:text-status-failed focus:outline-none focus:ring-2 focus:ring-status-failed focus:ring-offset-2 focus:ring-offset-bg-base"
            :title="strings.templates.actions.deleteTemplate"
          >
            <Trash2 :size="18" :stroke-width="2" />
          </button>
        </div>
      </div>
    </template>
  </BaseCard>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
