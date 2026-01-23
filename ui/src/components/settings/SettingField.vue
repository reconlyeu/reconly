<script setup lang="ts">
/**
 * SettingField - A unified component for displaying settings with source indicators.
 *
 * Shows different UI based on setting properties:
 * - Locked settings (editable=false): Shows lock icon + "Set via environment variable"
 * - Editable settings: Shows input field appropriate to the value type
 * - Source indicator: Badge showing where the value comes from (database/environment/default)
 */
import { computed } from 'vue';
import { strings } from '@/i18n/en';
import type { SettingValue, SettingSource } from '@/types/entities';

interface Props {
  /** The setting key (e.g., 'smtp_host') */
  settingKey: string;
  /** The setting value object with source and editable info */
  setting: SettingValue;
  /** Label to display */
  label: string;
  /** Optional description/help text */
  description?: string;
  /** Input type for editable fields */
  type?: 'text' | 'number' | 'password' | 'select';
  /** Options for select type */
  options?: { value: string; label: string }[];
  /** Whether the field is disabled (beyond the editable flag) */
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  disabled: false,
});

const emit = defineEmits<{
  (e: 'update', value: unknown): void;
}>();

// Source badge colors
const sourceBadgeClass = computed(() => {
  const classes: Record<SettingSource, string> = {
    database: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    environment: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300',
    default: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  };
  return classes[props.setting.source];
});

const sourceLabel = computed(() => {
  const labels: Record<SettingSource, string> = {
    database: strings.settings.source.database,
    environment: strings.settings.source.environment,
    default: strings.settings.source.default,
  };
  return labels[props.setting.source];
});

const isLocked = computed(() => !props.setting.editable);

const displayValue = computed(() => {
  if (props.setting.value === null || props.setting.value === undefined) {
    return '';
  }
  return String(props.setting.value);
});

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement | HTMLSelectElement;
  let value: unknown = target.value;

  if (props.type === 'number') {
    value = parseInt(target.value, 10);
  }

  emit('update', value);
};
</script>

<template>
  <div class="setting-field">
    <div class="flex items-center justify-between mb-1">
      <label :for="settingKey" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {{ label }}
      </label>
      <div class="flex items-center gap-2">
        <!-- Source badge -->
        <span
          :class="['text-xs px-2 py-0.5 rounded-full', sourceBadgeClass]"
          :title="strings.settings.source.valueFrom.replace('{source}', setting.source)"
        >
          {{ sourceLabel }}
        </span>
        <!-- Lock icon for non-editable -->
        <span v-if="isLocked" class="text-gray-400" :title="strings.settings.source.setViaEnv">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </span>
      </div>
    </div>

    <!-- Locked field display -->
    <div v-if="isLocked" class="relative">
      <input
        :id="settingKey"
        type="text"
        :value="displayValue"
        disabled
        class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-400 cursor-not-allowed"
      />
      <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">
        {{ strings.settings.source.setViaEnv }}
      </span>
    </div>

    <!-- Editable text/password input -->
    <input
      v-else-if="type === 'text' || type === 'password' || type === 'number'"
      :id="settingKey"
      :type="type"
      :value="displayValue"
      :disabled="disabled"
      @input="handleInput"
      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:bg-gray-100 disabled:cursor-not-allowed"
    />

    <!-- Editable select -->
    <select
      v-else-if="type === 'select'"
      :id="settingKey"
      :value="displayValue"
      :disabled="disabled"
      @change="handleInput"
      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:bg-gray-100 disabled:cursor-not-allowed"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>

    <!-- Description -->
    <p v-if="description" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
      {{ description }}
    </p>
  </div>
</template>

<style scoped>
.setting-field {
  margin-bottom: 1rem;
}
</style>
