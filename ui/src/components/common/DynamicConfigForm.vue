<script setup lang="ts">
/**
 * Dynamic configuration form component.
 *
 * Renders form fields based on a ConfigField[] schema from the backend.
 * Supports field types: string, integer, boolean, path, select, secret.
 *
 * @example
 * <DynamicConfigForm
 *   :schema="configFields"
 *   v-model:values="formValues"
 *   :options-data="{ models: modelsList }"
 *   @validation-change="handleValidation"
 * />
 */
import { ref, computed, watch } from 'vue';
import { strings } from '@/i18n/en';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import {
  FolderOpen,
  Eye,
  EyeOff,
  ChevronDown,
  AlertCircle,
} from 'lucide-vue-next';
import type { ConfigField } from '@/types/entities';

interface Props {
  /** Configuration field schema from backend */
  schema: ConfigField[];
  /** Current form values (v-model) */
  values: Record<string, unknown>;
  /** Dynamic options data for select fields using options_from */
  optionsData?: Record<string, Array<{ value: string; label: string }>>;
  /** Whether the form is disabled */
  disabled?: boolean;
  /** Whether to show field descriptions */
  showDescriptions?: boolean;
}

interface Emits {
  (e: 'update:values', values: Record<string, unknown>): void;
  (e: 'validation-change', isValid: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  optionsData: () => ({}),
  disabled: false,
  showDescriptions: true,
});

const emit = defineEmits<Emits>();

// Track which secret fields are visible
const visibleSecrets = ref<Set<string>>(new Set());

// Track touched fields for validation display
const touchedFields = ref<Set<string>>(new Set());

/**
 * Check if a value is empty (null, undefined, or empty string)
 */
function isEmptyValue(value: unknown): boolean {
  return value === null || value === undefined || value === '';
}

/**
 * Validate a field and return an error message if invalid, null if valid
 */
function validateField(field: ConfigField, value: unknown): string | null {
  // Required field validation
  if (field.required && isEmptyValue(value)) {
    return strings.dynamicForm.validation.required;
  }

  // Integer range validation
  if (field.type === 'integer' && !isEmptyValue(value)) {
    const numValue = Number(value);
    if (isNaN(numValue)) {
      return strings.dynamicForm.validation.invalidNumber;
    }
    if (field.min !== undefined && numValue < field.min) {
      return strings.dynamicForm.validation.minValue.replace('{min}', String(field.min));
    }
    if (field.max !== undefined && numValue > field.max) {
      return strings.dynamicForm.validation.maxValue.replace('{max}', String(field.max));
    }
  }

  return null;
}

/**
 * Get validation error for display (only if field is touched)
 */
function getFieldError(field: ConfigField): string | null {
  if (!touchedFields.value.has(field.key)) return null;
  return validateField(field, props.values[field.key]);
}

/**
 * Check if the entire form is valid
 */
const isValid = computed(() => {
  return props.schema.every((field) => validateField(field, props.values[field.key]) === null);
});

// Emit validation state changes
watch(isValid, (newValue) => {
  emit('validation-change', newValue);
}, { immediate: true });

/**
 * Update a single field value
 */
function updateField(key: string, value: unknown): void {
  touchedFields.value.add(key);
  emit('update:values', {
    ...props.values,
    [key]: value,
  });
}

/**
 * Handle blur event (mark field as touched)
 */
function handleBlur(key: string): void {
  touchedFields.value.add(key);
}

/**
 * Handle integer input - convert to number or empty string
 */
function handleIntegerInput(key: string, event: Event): void {
  const input = event.target as HTMLInputElement;
  const value = input.value ? Number(input.value) : '';
  updateField(key, value);
}

/**
 * Handle string input
 */
function handleStringInput(key: string, event: Event): void {
  const input = event.target as HTMLInputElement;
  updateField(key, input.value);
}

/**
 * Handle select change
 */
function handleSelectChange(key: string, event: Event): void {
  const select = event.target as HTMLSelectElement;
  updateField(key, select.value);
}

/**
 * Toggle secret field visibility
 */
function toggleSecretVisibility(key: string): void {
  const secrets = visibleSecrets.value;
  if (secrets.has(key)) {
    secrets.delete(key);
  } else {
    secrets.add(key);
  }
  // Trigger reactivity by creating a new Set
  visibleSecrets.value = new Set(secrets);
}

/**
 * Get options for a select field
 */
function getSelectOptions(field: ConfigField): Array<{ value: string; label: string }> {
  // Static options defined in the field
  if (field.options && field.options.length > 0) {
    return field.options;
  }

  // Dynamic options from optionsData
  if (field.options_from && props.optionsData[field.options_from]) {
    return props.optionsData[field.options_from];
  }

  return [];
}

/**
 * Check if a field is editable
 */
function isFieldEditable(field: ConfigField): boolean {
  return !props.disabled && field.editable !== false;
}

/**
 * Get the current value for a field, with type-appropriate default
 */
function getFieldValue(field: ConfigField): unknown {
  const value = props.values[field.key];
  if (value !== undefined && value !== null) return value;

  // Return field default if available
  if (field.default !== undefined) return field.default;

  // Type-appropriate defaults
  if (field.type === 'boolean') return false;
  return '';
}

// Expose isValid for parent components
defineExpose({
  isValid,
});
</script>

<template>
  <div class="space-y-5">
    <div
      v-for="field in schema"
      :key="field.key"
      class="space-y-2"
    >
      <!-- Label with required indicator and env var badge -->
      <div class="flex items-center justify-between">
        <label
          :for="`field-${field.key}`"
          class="text-sm font-medium text-text-primary"
        >
          {{ field.label }}
          <span v-if="field.required" class="text-status-failed">*</span>
        </label>
        <span
          v-if="field.env_var && !isFieldEditable(field)"
          class="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400"
        >
          {{ strings.dynamicForm.setViaEnv }}
        </span>
      </div>

      <!-- String Input -->
      <input
        v-if="field.type === 'string'"
        :id="`field-${field.key}`"
        type="text"
        :value="getFieldValue(field)"
        :placeholder="field.placeholder || ''"
        :disabled="!isFieldEditable(field)"
        @input="handleStringInput(field.key, $event)"
        @blur="handleBlur(field.key)"
        class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
        :class="{ 'border-status-failed': getFieldError(field) }"
      />

      <!-- Integer Input -->
      <input
        v-else-if="field.type === 'integer'"
        :id="`field-${field.key}`"
        type="number"
        :value="getFieldValue(field)"
        :placeholder="field.placeholder || ''"
        :min="field.min"
        :max="field.max"
        :disabled="!isFieldEditable(field)"
        @input="handleIntegerInput(field.key, $event)"
        @blur="handleBlur(field.key)"
        class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
        :class="{ 'border-status-failed': getFieldError(field) }"
      />

      <!-- Boolean Toggle -->
      <div
        v-else-if="field.type === 'boolean'"
        class="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-surface p-3"
      >
        <span class="text-sm text-text-secondary">{{ field.description }}</span>
        <ToggleSwitch
          :model-value="Boolean(getFieldValue(field))"
          :disabled="!isFieldEditable(field)"
          @update:model-value="updateField(field.key, $event)"
        />
      </div>

      <!-- Path Input -->
      <div v-else-if="field.type === 'path'" class="relative">
        <div class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
          <FolderOpen :size="18" />
        </div>
        <input
          :id="`field-${field.key}`"
          type="text"
          :value="getFieldValue(field)"
          :placeholder="field.placeholder || strings.dynamicForm.pathPlaceholder"
          :disabled="!isFieldEditable(field)"
          @input="handleStringInput(field.key, $event)"
          @blur="handleBlur(field.key)"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 font-mono text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          :class="{ 'border-status-failed': getFieldError(field) }"
        />
      </div>

      <!-- Select Dropdown -->
      <div v-else-if="field.type === 'select'" class="relative">
        <select
          :id="`field-${field.key}`"
          :value="getFieldValue(field)"
          :disabled="!isFieldEditable(field)"
          @change="handleSelectChange(field.key, $event)"
          @blur="handleBlur(field.key)"
          class="w-full appearance-none rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 pr-10 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
          :class="{ 'border-status-failed': getFieldError(field) }"
        >
          <option value="" disabled>{{ strings.dynamicForm.selectPlaceholder }}</option>
          <option
            v-for="option in getSelectOptions(field)"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <div class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted">
          <ChevronDown :size="18" />
        </div>
      </div>

      <!-- Secret Input (Password with toggle) -->
      <div v-else-if="field.type === 'secret' || field.secret" class="relative">
        <input
          :id="`field-${field.key}`"
          :type="visibleSecrets.has(field.key) ? 'text' : 'password'"
          :value="getFieldValue(field)"
          :placeholder="field.placeholder || strings.dynamicForm.secretPlaceholder"
          :disabled="!isFieldEditable(field)"
          @input="handleStringInput(field.key, $event)"
          @blur="handleBlur(field.key)"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 pr-10 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
          :class="{ 'border-status-failed': getFieldError(field) }"
        />
        <button
          v-if="isFieldEditable(field)"
          type="button"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary focus:outline-none"
          @click="toggleSecretVisibility(field.key)"
          :aria-label="visibleSecrets.has(field.key) ? strings.dynamicForm.hideSecret : strings.dynamicForm.showSecret"
        >
          <Eye v-if="!visibleSecrets.has(field.key)" :size="18" />
          <EyeOff v-else :size="18" />
        </button>
      </div>

      <!-- Description (for non-boolean fields) -->
      <p
        v-if="showDescriptions && field.description && field.type !== 'boolean'"
        class="text-xs text-text-muted"
      >
        {{ field.description }}
      </p>

      <!-- Validation Error -->
      <div
        v-if="getFieldError(field)"
        class="flex items-center gap-1.5 text-xs text-status-failed"
      >
        <AlertCircle :size="14" />
        <span>{{ getFieldError(field) }}</span>
      </div>
    </div>

    <!-- Empty state when no fields -->
    <div
      v-if="schema.length === 0"
      class="text-center text-sm text-text-muted py-4"
    >
      {{ strings.dynamicForm.noFields }}
    </div>
  </div>
</template>
