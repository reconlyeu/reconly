<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { tagsApi } from '@/services/api';
import { X, Plus } from 'lucide-vue-next';
import type { TagSuggestion } from '@/types/entities';

interface Props {
  modelValue: string[];
  placeholder?: string;
  disabled?: boolean;
  maxTags?: number;
}

interface Emits {
  (e: 'update:modelValue', value: string[]): void;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Add tag...',
  disabled: false,
  maxTags: 10,
});

const emit = defineEmits<Emits>();

// Local state
const inputValue = ref('');
const isOpen = ref(false);
const selectedIndex = ref(-1);
const inputRef = ref<HTMLInputElement | null>(null);
const containerRef = ref<HTMLDivElement | null>(null);

// Fetch tag suggestions
const { data: suggestionsData, refetch: refetchSuggestions } = useQuery({
  queryKey: ['tagSuggestions', inputValue],
  queryFn: () => tagsApi.getSuggestions(inputValue.value, 10),
  enabled: false, // Manual control
  staleTime: 10000,
});

// Filter suggestions to exclude already-selected tags
const suggestions = computed(() => {
  if (!suggestionsData.value?.suggestions) return [];
  return suggestionsData.value.suggestions.filter(
    (s: TagSuggestion) => !props.modelValue.includes(s.name)
  );
});

// Show "Create new tag" option when input has value and doesn't match suggestions
const showCreateOption = computed(() => {
  const trimmedInput = inputValue.value.trim();
  if (!trimmedInput) return false;
  if (props.modelValue.includes(trimmedInput)) return false;
  // Show create option if the exact match doesn't exist
  return !suggestions.value.some((s) => s.name.toLowerCase() === trimmedInput.toLowerCase());
});

// Debounced fetch
let debounceTimeout: ReturnType<typeof setTimeout>;
watch(inputValue, (newValue) => {
  clearTimeout(debounceTimeout);
  if (newValue.trim()) {
    debounceTimeout = setTimeout(() => {
      refetchSuggestions();
    }, 200);
  }
});

// Open dropdown when input is focused
const handleFocus = () => {
  if (!props.disabled) {
    isOpen.value = true;
    if (inputValue.value.trim()) {
      refetchSuggestions();
    }
  }
};

// Close dropdown on click outside
const handleClickOutside = (event: MouseEvent) => {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false;
    selectedIndex.value = -1;
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
  clearTimeout(debounceTimeout);
});

// Keyboard navigation
const handleKeydown = (event: KeyboardEvent) => {
  const maxIndex = suggestions.value.length + (showCreateOption.value ? 0 : -1);

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault();
      selectedIndex.value = Math.min(selectedIndex.value + 1, maxIndex);
      break;
    case 'ArrowUp':
      event.preventDefault();
      selectedIndex.value = Math.max(selectedIndex.value - 1, -1);
      break;
    case 'Enter':
      event.preventDefault();
      if (selectedIndex.value >= 0 && selectedIndex.value < suggestions.value.length) {
        addTag(suggestions.value[selectedIndex.value].name);
      } else if (selectedIndex.value === suggestions.value.length && showCreateOption.value) {
        addTag(inputValue.value.trim());
      } else if (inputValue.value.trim()) {
        addTag(inputValue.value.trim());
      }
      break;
    case 'Escape':
      isOpen.value = false;
      selectedIndex.value = -1;
      break;
    case 'Backspace':
      if (!inputValue.value && props.modelValue.length > 0) {
        removeTag(props.modelValue[props.modelValue.length - 1]);
      }
      break;
  }
};

// Add a tag
const addTag = (tagName: string) => {
  const trimmed = tagName.trim();
  if (!trimmed) return;
  if (props.modelValue.length >= props.maxTags) return;
  if (props.modelValue.includes(trimmed)) return;

  emit('update:modelValue', [...props.modelValue, trimmed]);
  inputValue.value = '';
  selectedIndex.value = -1;
  isOpen.value = false;
  inputRef.value?.focus();
};

// Remove a tag
const removeTag = (tagName: string) => {
  emit('update:modelValue', props.modelValue.filter((t) => t !== tagName));
  inputRef.value?.focus();
};

// Handle suggestion click
const handleSuggestionClick = (suggestion: TagSuggestion) => {
  addTag(suggestion.name);
};

// Handle create new click
const handleCreateClick = () => {
  addTag(inputValue.value.trim());
};
</script>

<template>
  <div ref="containerRef" class="relative">
    <!-- Tags and Input Container -->
    <div
      class="flex flex-wrap items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-surface px-3 py-2 transition-colors focus-within:border-border-default"
      :class="{ 'opacity-50 cursor-not-allowed': disabled }"
    >
      <!-- Selected Tags -->
      <span
        v-for="tag in modelValue"
        :key="tag"
        class="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2.5 py-1 text-sm text-text-secondary"
      >
        {{ tag }}
        <button
          v-if="!disabled"
          type="button"
          class="rounded-full p-0.5 text-text-muted hover:bg-bg-surface hover:text-text-primary focus:outline-none"
          @click.stop="removeTag(tag)"
        >
          <X :size="12" />
        </button>
      </span>

      <!-- Input -->
      <input
        ref="inputRef"
        v-model="inputValue"
        type="text"
        :placeholder="modelValue.length === 0 ? placeholder : ''"
        :disabled="disabled || modelValue.length >= maxTags"
        class="flex-1 min-w-[100px] bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed"
        @focus="handleFocus"
        @keydown="handleKeydown"
      />
    </div>

    <!-- Suggestions Dropdown -->
    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="isOpen && (suggestions.length > 0 || showCreateOption)"
        class="absolute z-50 mt-1 w-full rounded-lg border border-border-subtle bg-bg-elevated shadow-lg"
      >
        <ul class="max-h-48 overflow-auto py-1">
          <!-- Existing tags suggestions -->
          <li
            v-for="(suggestion, index) in suggestions"
            :key="suggestion.name"
            class="flex cursor-pointer items-center justify-between px-3 py-2 text-sm transition-colors"
            :class="{
              'bg-bg-hover': selectedIndex === index,
              'text-text-primary': selectedIndex === index,
              'text-text-secondary': selectedIndex !== index,
            }"
            @click="handleSuggestionClick(suggestion)"
            @mouseenter="selectedIndex = index"
          >
            <span>{{ suggestion.name }}</span>
            <span class="text-xs text-text-muted">{{ suggestion.digest_count }} digests</span>
          </li>

          <!-- Create new tag option -->
          <li
            v-if="showCreateOption"
            class="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm transition-colors"
            :class="{
              'bg-bg-hover': selectedIndex === suggestions.length,
              'text-text-primary': selectedIndex === suggestions.length,
              'text-text-secondary': selectedIndex !== suggestions.length,
            }"
            @click="handleCreateClick"
            @mouseenter="selectedIndex = suggestions.length"
          >
            <Plus :size="14" />
            <span>Create "{{ inputValue.trim() }}"</span>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>
