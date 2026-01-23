<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import * as z from 'zod';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { promptTemplatesApi } from '@/services/api';
import type { PromptTemplate } from '@/types/entities';
import { X, Loader2, Languages, AlignLeft, MessageSquare, Copy } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  isOpen: boolean;
  template?: PromptTemplate | null;
}

interface Emits {
  (e: 'close'): void;
  (e: 'success'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const queryClient = useQueryClient();

// Validation schema
const formSchema = toTypedSchema(
  z.object({
    name: z.string().min(1, 'Name is required').max(200, 'Name is too long'),
    description: z.string().max(500, 'Description is too long').optional(),
    language: z.string().min(1, 'Language is required'),
    target_length: z.number().min(50).max(1000),
    system_prompt: z.string().min(10, 'System prompt must be at least 10 characters'),
    user_prompt_template: z.string().min(10, 'Template content must be at least 10 characters'),
  })
);

const { defineField, handleSubmit, resetForm, errors } = useForm({
  validationSchema: formSchema,
  initialValues: {
    name: '',
    description: '',
    language: 'en',
    target_length: 150,
    system_prompt: 'You are an AI assistant.',
    user_prompt_template: 'Summarize: {content}',
  },
});

const [name, nameAttrs] = defineField('name');
const [description, descriptionAttrs] = defineField('description');
const [language, languageAttrs] = defineField('language');
const [target_length, targetLengthAttrs] = defineField('target_length');
const [system_prompt, systemPromptAttrs] = defineField('system_prompt');
const [user_prompt_template, userPromptTemplateAttrs] = defineField('user_prompt_template');

// Watch for template prop changes (edit mode)
watch(
  () => props.template,
  (newTemplate) => {
    if (newTemplate) {
      resetForm({
        values: {
          name: newTemplate.name,
          description: newTemplate.description || '',
          language: newTemplate.language,
          target_length: newTemplate.target_length,
          system_prompt: newTemplate.system_prompt,
          user_prompt_template: newTemplate.user_prompt_template,
        },
      });
    } else {
      resetForm();
    }
  },
  { immediate: true }
);

const isEditMode = computed(() => !!props.template);
const isCopying = ref(false);

// Create/Update mutation
const saveMutation = useMutation({
  mutationFn: async (data: any) => {
    if (isEditMode.value && props.template && !isCopying.value) {
      return await promptTemplatesApi.update(props.template.id, data);
    } else {
      // Create new (either new template or copy)
      return await promptTemplatesApi.create(data);
    }
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    emit('success');
    emit('close');
    resetForm();
    isCopying.value = false;
  },
  onError: (error: any) => {
    console.error('Failed to save prompt template:', error);
    isCopying.value = false;
  },
});

// Watch for modal open to reset mutation state
watch(
  () => props.isOpen,
  (isOpen) => {
    if (isOpen) {
      saveMutation.reset();
    }
  }
);

// Computed for reactive pending state
const isSaving = computed(() => saveMutation.isPending.value);

const onSubmit = handleSubmit((values) => {
  saveMutation.mutate(values);
});

const handleClose = () => {
  if (!isSaving.value) {
    emit('close');
    resetForm();
    isCopying.value = false;
  }
};

const handleCreateCopy = handleSubmit((values) => {
  isCopying.value = true;
  saveMutation.mutate({
    ...values,
    name: `Copy of ${values.name}`,
  });
});

const languages = [
  'English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese',
  'Dutch', 'Russian', 'Chinese', 'Japanese', 'Korean', 'Arabic'
];
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="handleClose"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" />

        <!-- Modal -->
        <div
          class="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orb -->
          <div class="pointer-events-none absolute -right-20 -top-20 h-40 w-40 rounded-full bg-purple-500/20 blur-3xl" />

          <!-- Sticky Header -->
          <div class="sticky top-0 z-10 border-b border-border-subtle bg-bg-elevated/95 backdrop-blur-sm p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10">
                  <Languages :size="20" class="text-purple-400" :stroke-width="2" />
                </div>
                <h2 class="text-2xl font-bold text-text-primary">
                  {{ isEditMode ? strings.templates.editPromptTemplate : strings.templates.createPromptTemplate }}
                </h2>
              </div>
              <button
                @click="handleClose"
                :disabled="isSaving"
                class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
              >
                <X :size="20" />
              </button>
            </div>
          </div>

          <!-- Form -->
          <form @submit.prevent="onSubmit" class="p-6 space-y-6">
            <!-- Name -->
            <div>
              <label for="name" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.templates.templateName }}
              </label>
              <input
                id="name"
                v-model="name"
                v-bind="nameAttrs"
                type="text"
                :placeholder="strings.templates.placeholders.name"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.name
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.name" class="mt-2 text-sm text-status-failed">{{ errors.name }}</p>
              </Transition>
            </div>

            <!-- Description -->
            <div>
              <label for="description" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.templates.fields.description }} <span class="text-text-muted">({{ strings.common.optional }})</span>
              </label>
              <textarea
                id="description"
                v-model="description"
                v-bind="descriptionAttrs"
                rows="2"
                :placeholder="strings.templates.placeholders.description"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all resize-none"
                :class="
                  errors.description
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.description" class="mt-2 text-sm text-status-failed">{{ errors.description }}</p>
              </Transition>
            </div>

            <!-- Language and Target Length -->
            <div class="grid gap-6 md:grid-cols-2">
              <!-- Language -->
              <div>
                <label for="language" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.templates.fields.language }}
                </label>
                <div class="relative">
                  <Languages class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
                  <select
                    id="language"
                    v-model="language"
                    v-bind="languageAttrs"
                    class="w-full rounded-lg border bg-bg-surface pl-10 pr-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                    :class="
                      errors.language
                        ? 'border-status-failed focus:ring-status-failed'
                        : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                    "
                  >
                    <option v-for="lang in languages" :key="lang" :value="lang">{{ lang }}</option>
                  </select>
                </div>
                <Transition name="error">
                  <p v-if="errors.language" class="mt-2 text-sm text-status-failed">{{ errors.language }}</p>
                </Transition>
              </div>

              <!-- Target Length -->
              <div>
                <label for="target_length" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.templates.fields.targetLength }}
                </label>
                <div class="relative">
                  <AlignLeft class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
                  <select
                    id="target_length"
                    v-model.number="target_length"
                    v-bind="targetLengthAttrs"
                    class="w-full rounded-lg border bg-bg-surface pl-10 pr-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                    :class="
                      errors.target_length
                        ? 'border-status-failed focus:ring-status-failed'
                        : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                    "
                  >
                    <option :value="100">{{ strings.templates.targetLengths.brief }}</option>
                    <option :value="150">{{ strings.templates.targetLengths.standard }}</option>
                    <option :value="300">{{ strings.templates.targetLengths.detailed }}</option>
                    <option :value="500">{{ strings.templates.targetLengths.comprehensive }}</option>
                  </select>
                </div>
                <Transition name="error">
                  <p v-if="errors.target_length" class="mt-2 text-sm text-status-failed">{{ errors.target_length }}</p>
                </Transition>
              </div>
            </div>

            <!-- Template Content -->
            <div>
              <label for="user_prompt_template" class="mb-2 block text-sm font-medium text-text-primary">
                {{ strings.templates.templateContent }}
              </label>
              <textarea
                id="user_prompt_template"
                v-model="user_prompt_template"
                v-bind="userPromptTemplateAttrs"
                rows="12"
                placeholder="You are an AI assistant that creates concise summaries of articles.

Your task is to:
1. Extract the main points from the provided content
2. Organize them in a clear, logical structure
3. Write in {language} language
4. Keep the summary {target_length}

Content to summarize:
{content}"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all resize-none"
                :class="
                  errors.user_prompt_template
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <p class="mt-2 text-xs text-text-muted">
                Use <code class="rounded bg-bg-hover px-1 py-0.5 font-mono text-purple-400">{language}</code>,
                <code class="rounded bg-bg-hover px-1 py-0.5 font-mono text-purple-400">{target_length}</code>, and
                <code class="rounded bg-bg-hover px-1 py-0.5 font-mono text-purple-400">{content}</code> as variables
              </p>
              <Transition name="error">
                <p v-if="errors.user_prompt_template" class="mt-2 text-sm text-status-failed">{{ errors.user_prompt_template }}</p>
              </Transition>
            </div>

            <!-- Actions -->
            <div class="flex gap-3 pt-4">
              <button
                type="button"
                @click="handleClose"
                :disabled="isSaving"
                class="flex-1 rounded-lg border border-border-subtle bg-bg-surface px-6 py-3 font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50"
              >
                {{ strings.common.cancel }}
              </button>
              <button
                type="submit"
                :disabled="isSaving"
                class="flex-1 rounded-lg bg-accent-primary px-6 py-3 font-medium text-white transition-all hover:bg-accent-primary-hover disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isSaving"
                  :size="18"
                  class="animate-spin"
                />
                {{ isSaving ? strings.templates.saving : (isEditMode ? strings.templates.updateTemplate : strings.templates.createTemplate) }}
              </button>
            </div>

            <!-- Create Copy Link (only in edit mode) -->
            <div v-if="isEditMode" class="pt-3 text-center">
              <button
                type="button"
                @click="handleCreateCopy"
                :disabled="isSaving"
                class="inline-flex items-center gap-1.5 text-sm text-text-muted transition-all hover:text-accent-primary hover:underline underline-offset-2 disabled:opacity-50"
              >
                <Copy :size="14" />
                {{ strings.templates.actions.createCopy }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95) translateY(20px);
  opacity: 0;
}

/* Error message transitions */
.error-enter-active,
.error-leave-active {
  transition: all 0.2s ease;
}

.error-enter-from,
.error-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Custom scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: var(--color-bg-surface);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: var(--color-bg-hover);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: var(--color-border-default);
}
</style>
