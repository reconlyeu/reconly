<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { tagsApi } from '@/services/api';
import { Tag, X, Trash2, ChevronDown } from 'lucide-vue-next';
import type { Tag as TagType } from '@/types/entities';
import { strings } from '@/i18n/en';

interface Props {
  modelValue: string | null;
}

interface Emits {
  (e: 'update:modelValue', value: string | null): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const queryClient = useQueryClient();

// Dropdown state
const isOpen = ref(false);
const containerRef = ref<HTMLDivElement | null>(null);
const confirmingDelete = ref<number | null>(null);

// Fetch tags
const { data: tags, isLoading } = useQuery({
  queryKey: ['tags'],
  queryFn: () => tagsApi.list(),
  staleTime: 60000,
});

// Count unused tags
const unusedCount = computed(() => {
  if (!tags.value) return 0;
  return tags.value.filter((t) => (t.digest_count || 0) === 0).length;
});

// Selected tag display
const selectedTag = computed(() => {
  if (!props.modelValue || !tags.value) return null;
  return tags.value.find((t) => t.name === props.modelValue);
});

// Delete mutations
const deleteMutation = useMutation({
  mutationFn: (tagId: number) => tagsApi.delete(tagId),
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['tags'] });
    // If the deleted tag was selected, clear the filter
    if (props.modelValue === data.tag_name) {
      emit('update:modelValue', null);
    }
    confirmingDelete.value = null;
  },
});

const deleteUnusedMutation = useMutation({
  mutationFn: () => tagsApi.deleteUnused(),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['tags'] });
  },
});

// Event handlers
const toggleDropdown = () => {
  isOpen.value = !isOpen.value;
  if (!isOpen.value) {
    confirmingDelete.value = null;
  }
};

const selectTag = (tagName: string | null) => {
  emit('update:modelValue', tagName);
  isOpen.value = false;
  confirmingDelete.value = null;
};

const handleDeleteClick = (tag: TagType, event: Event) => {
  event.stopPropagation();
  if (tag.digest_count && tag.digest_count > 0) {
    // Show confirmation for tags with digests
    confirmingDelete.value = tag.id;
  } else {
    // Delete immediately for unused tags
    deleteMutation.mutate(tag.id);
  }
};

const confirmDelete = (tagId: number, event: Event) => {
  event.stopPropagation();
  deleteMutation.mutate(tagId);
};

const cancelDelete = (event: Event) => {
  event.stopPropagation();
  confirmingDelete.value = null;
};

const handleDeleteUnused = () => {
  deleteUnusedMutation.mutate();
};

// Close dropdown on click outside
const handleClickOutside = (event: MouseEvent) => {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false;
    confirmingDelete.value = null;
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div ref="containerRef" class="relative">
    <!-- Dropdown trigger -->
    <button
      type="button"
      class="flex w-full md:w-48 items-center justify-between rounded-lg border border-border-subtle bg-bg-surface px-3 py-2.5 text-left text-text-primary transition-colors hover:bg-bg-hover focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
      @click="toggleDropdown"
    >
      <span class="flex items-center gap-2">
        <Tag class="text-text-muted" :size="18" />
        <span v-if="selectedTag" class="truncate">
          {{ selectedTag.name }}
        </span>
        <span v-else class="text-text-secondary">{{ strings.common.tagFilter.allTags }}</span>
      </span>
      <ChevronDown
        :size="16"
        class="text-text-muted transition-transform"
        :class="{ 'rotate-180': isOpen }"
      />
    </button>

    <!-- Dropdown menu -->
    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="absolute z-50 mt-1 w-full md:w-48 overflow-hidden rounded-lg border border-border-subtle bg-bg-elevated shadow-lg"
      >
        <!-- All Tags option -->
        <div
          class="flex cursor-pointer items-center justify-between border-b border-border-subtle px-3 py-2.5 transition-colors hover:bg-bg-hover"
          :class="{ 'bg-bg-hover': !modelValue }"
          @click="selectTag(null)"
        >
          <span class="font-medium text-text-primary">{{ strings.common.tagFilter.allTags }}</span>
        </div>

        <!-- Tags list -->
        <ul class="max-h-64 overflow-y-auto overflow-x-hidden py-1">
          <li v-if="isLoading" class="px-3 py-2 text-sm text-text-muted">{{ strings.common.tagFilter.loading }}</li>
          <li v-else-if="!tags?.length" class="px-3 py-2 text-sm text-text-muted">{{ strings.common.tagFilter.noTags }}</li>
          <template v-else>
            <li
              v-for="tag in tags"
              :key="tag.id"
              class="group relative w-full overflow-hidden"
            >
              <!-- Confirmation state -->
              <div
                v-if="confirmingDelete === tag.id"
                class="flex items-center justify-between bg-status-error/10 px-3 py-2"
              >
                <span class="text-sm text-status-error">{{ strings.common.tagFilter.confirmDelete.replace('{count}', String(tag.digest_count)) }}</span>
                <div class="flex items-center gap-1">
                  <button
                    type="button"
                    class="rounded px-2 py-1 text-xs font-medium text-text-secondary hover:bg-bg-surface"
                    @click="cancelDelete"
                  >
                    {{ strings.common.tagFilter.no }}
                  </button>
                  <button
                    type="button"
                    class="rounded bg-status-error px-2 py-1 text-xs font-medium text-white hover:bg-status-error/80"
                    @click="confirmDelete(tag.id, $event)"
                  >
                    {{ strings.common.tagFilter.yes }}
                  </button>
                </div>
              </div>

              <!-- Normal state -->
              <div
                v-else
                class="flex cursor-pointer items-center justify-between px-3 py-2 transition-colors hover:bg-bg-hover"
                :class="{ 'bg-bg-hover': modelValue === tag.name }"
                @click="selectTag(tag.name)"
              >
                <span class="flex min-w-0 flex-1 items-center gap-2">
                  <span class="truncate text-sm text-text-primary">{{ tag.name }}</span>
                  <span class="shrink-0 text-xs text-text-muted">({{ tag.digest_count || 0 }})</span>
                </span>
                <button
                  type="button"
                  class="shrink-0 rounded p-1 text-text-muted opacity-0 transition-all hover:bg-bg-surface hover:text-status-error group-hover:opacity-100"
                  :class="{ 'opacity-100': deleteMutation.isPending.value }"
                  :disabled="deleteMutation.isPending.value"
                  @click="handleDeleteClick(tag, $event)"
                >
                  <X :size="14" />
                </button>
              </div>
            </li>
          </template>
        </ul>

        <!-- Delete unused action -->
        <div
          v-if="unusedCount > 0"
          class="border-t border-border-subtle"
        >
          <button
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-status-error transition-colors hover:bg-status-error/10 disabled:opacity-50"
            :disabled="deleteUnusedMutation.isPending.value"
            @click="handleDeleteUnused"
          >
            <Trash2 :size="14" />
            <span>
              {{ deleteUnusedMutation.isPending.value ? strings.common.tagFilter.deleting : strings.common.tagFilter.deleteUnused.replace('{count}', String(unusedCount)) }}
            </span>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
