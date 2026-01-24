<script setup lang="ts">
/**
 * Export dropdown component showing enabled exporters.
 * Used for single digest export and bulk export actions.
 */
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { Download, ChevronDown } from 'lucide-vue-next';
import { Icon } from '@iconify/vue';
import { useEnabledExporters } from '@/composables/useExporters';
import type { Exporter } from '@/types/entities';
import { strings } from '@/i18n/en';

// Default fallback icon for exporters without metadata.icon
const FALLBACK_ICON = 'mdi:file-export-outline';

interface Props {
  /** Size variant */
  size?: 'sm' | 'md';
  /** Show as icon-only button (no text) */
  iconOnly?: boolean;
  /** Custom button class */
  buttonClass?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Open dropdown upward (for bottom-positioned triggers) */
  openUp?: boolean;
}

interface Emits {
  (e: 'select', exporter: Exporter): void;
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  iconOnly: false,
  disabled: false,
  loading: false,
  openUp: false,
});

const emit = defineEmits<Emits>();

const { exporters: configuredExporters, isLoading } = useEnabledExporters();

// Built-in markdown download - always available as baseline feature
const builtInMarkdownExporter: Exporter = {
  name: 'markdown',
  description: 'Export as Markdown file',
  content_type: 'text/markdown',
  enabled: true,
  supports_direct_export: false,
  file_extension: 'md',
  config_schema: { fields: [], supports_direct_export: false },
  is_configured: true,
  can_enable: true,
  is_extension: false,
  metadata: {
    name: 'markdown',
    display_name: 'Markdown',
    description: 'Export as Markdown file',
    icon: 'mdi:language-markdown',
    file_extension: 'md',
    mime_type: 'text/markdown',
    ui_color: null,
  },
};

// Combine built-in markdown with configured exporters (avoid duplicates)
const exporters = computed(() => {
  const configured = configuredExporters.value || [];
  // Check if markdown is already configured
  const hasMarkdown = configured.some(e => e.name.toLowerCase() === 'markdown');
  if (hasMarkdown) {
    return configured;
  }
  // Add built-in markdown as first option
  return [builtInMarkdownExporter, ...configured];
});

// Dropdown state
const isOpen = ref(false);
const containerRef = ref<HTMLDivElement | null>(null);
const buttonRef = ref<HTMLButtonElement | null>(null);
const dropdownPosition = ref({ top: 0, left: 0 });
const opensUpward = ref(false);

const updateDropdownPosition = () => {
  if (!buttonRef.value) return;

  const rect = buttonRef.value.getBoundingClientRect();
  const dropdownHeight = 200; // Approximate max height
  const viewportHeight = window.innerHeight;

  // Check if dropdown would overflow bottom of viewport
  const spaceBelow = viewportHeight - rect.bottom;
  opensUpward.value = props.openUp || spaceBelow < dropdownHeight;

  if (opensUpward.value) {
    // Position above the button (top of dropdown aligns with top of button, then translate up)
    dropdownPosition.value = {
      top: rect.top + window.scrollY - 4,
      left: rect.right + window.scrollX,
    };
  } else {
    // Position below the button
    dropdownPosition.value = {
      top: rect.bottom + window.scrollY + 4,
      left: rect.right + window.scrollX,
    };
  }
};

const toggleDropdown = async () => {
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    await nextTick();
    updateDropdownPosition();
  }
};

const selectExporter = (exporter: Exporter, event: Event) => {
  event.stopPropagation();
  event.preventDefault();
  isOpen.value = false;
  emit('select', exporter);
};

/**
 * Get the icon string for an exporter.
 * Uses metadata.icon if available, otherwise falls back to a generic export icon.
 */
const getExporterIcon = (exporter: Exporter): string => {
  return exporter.metadata?.icon || FALLBACK_ICON;
};

// Close dropdown on click outside
const handleClickOutside = (event: MouseEvent) => {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false;
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
      ref="buttonRef"
      type="button"
      :disabled="disabled || loading"
      :class="[
        buttonClass || (iconOnly
          ? 'rounded-lg p-1.5 text-text-muted transition-colors hover:bg-amber-400/10 hover:text-amber-400 disabled:opacity-50 disabled:cursor-not-allowed'
          : 'flex items-center gap-1.5 rounded-lg bg-amber-400/10 px-3 py-1.5 text-sm font-medium text-amber-400 transition-all hover:bg-amber-400/20 disabled:opacity-50 disabled:cursor-not-allowed'),
        { 'cursor-wait': loading }
      ]"
      :title="iconOnly ? strings.common.exportDropdown.title : undefined"
      @click.stop="toggleDropdown"
    >
      <Download
        :size="size === 'sm' ? 14 : 16"
        :stroke-width="2"
        :class="{ 'animate-pulse': loading }"
      />
      <template v-if="!iconOnly">
        <span>{{ loading ? strings.common.exportDropdown.exporting : strings.common.exportDropdown.button }}</span>
        <ChevronDown
          :size="14"
          class="transition-transform"
          :class="{ 'rotate-180': isOpen }"
        />
      </template>
    </button>

    <!-- Dropdown menu - teleported to body to escape overflow:hidden containers -->
    <Teleport to="body">
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
          class="fixed z-[9999] min-w-[180px] overflow-hidden rounded-lg border border-border-subtle bg-bg-elevated shadow-lg"
          :style="{
            top: `${dropdownPosition.top}px`,
            left: `${dropdownPosition.left}px`,
            transform: opensUpward ? 'translate(-100%, -100%)' : 'translateX(-100%)'
          }"
          @click.stop
        >
          <!-- Exporters list (always has at least built-in markdown) -->
          <ul class="py-1">
            <li
              v-for="exporter in exporters"
              :key="exporter.name"
              class="flex items-center gap-2 cursor-pointer px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
              @click="selectExporter(exporter, $event)"
            >
              <Icon :icon="getExporterIcon(exporter)" :width="14" :height="14" class="text-text-muted flex-shrink-0" />
              <span>{{ exporter.metadata?.display_name || exporter.name }}</span>
            </li>
          </ul>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
