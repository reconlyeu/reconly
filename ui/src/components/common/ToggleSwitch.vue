<script setup lang="ts">
/**
 * Reusable toggle switch component.
 * Extracted from SourceCard pattern.
 */

interface Props {
  modelValue: boolean;
  disabled?: boolean;
  size?: 'sm' | 'md';
  label?: string;
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  size: 'md',
});

const emit = defineEmits<Emits>();

const toggle = () => {
  if (!props.disabled) {
    emit('update:modelValue', !props.modelValue);
  }
};

// Size-based classes
const sizeClasses = {
  sm: {
    track: 'h-5 w-10',
    thumb: 'h-3.5 w-3.5',
    translateOn: 'translate-x-5',
    translateOff: 'translate-x-1',
  },
  md: {
    track: 'h-7 w-14',
    thumb: 'h-5 w-5',
    translateOn: 'translate-x-8',
    translateOff: 'translate-x-1',
  },
};
</script>

<template>
  <button
    type="button"
    @click="toggle"
    class="relative inline-flex items-center rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
    :class="[
      sizeClasses[size].track,
      modelValue ? 'bg-accent-primary' : 'bg-bg-hover',
      disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
    ]"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="label"
    :disabled="disabled"
  >
    <span
      class="inline-block transform rounded-full bg-white shadow-lg transition-transform duration-300"
      :class="[
        sizeClasses[size].thumb,
        modelValue ? sizeClasses[size].translateOn : sizeClasses[size].translateOff,
      ]"
    />
  </button>
</template>
