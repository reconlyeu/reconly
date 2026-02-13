<script setup lang="ts">
import { computed } from 'vue';
import type { Exporter } from '@/types/entities';
import { Mail, Webhook, Download, AlertTriangle, ExternalLink } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  enabledExporters: Exporter[];
  allDirectExportExporters: Exporter[];
  disabledConfiguredExporters: Exporter[];
  exportSettings: Record<string, any> | null;
  errors?: Record<string, string | undefined>;
}

const props = defineProps<Props>();

const outputConfig = defineModel<{ email_recipients?: string; webhook_url?: string }>('outputConfig', { required: true });
const autoExportConfig = defineModel<Record<string, { enabled: boolean; path: string }>>('autoExportConfig', { required: true });

const getGlobalExportPath = (exporterName: string): string | null => {
  if (!props.exportSettings?.categories?.export) return null;

  // Use path_setting_key from exporter metadata for the correct setting key
  // Settings are stored with exporter prefix: obsidian.vault_path, json.export_path, etc.
  const exporter = props.allDirectExportExporters?.find(e => e.name === exporterName);
  const pathKey = exporter?.metadata?.path_setting_key || 'export_path';
  return props.exportSettings.categories.export[`${exporterName}.${pathKey}`]?.value as string || null;
};

// Check if an exporter has a path configured (either global or local override)
const hasPathConfigured = (exporterName: string): boolean => {
  const localPath = autoExportConfig.value[exporterName]?.path;
  if (localPath) return true;
  return !!getGlobalExportPath(exporterName);
};
</script>

<template>
  <div>
    <!-- Section 5: Output Configuration -->
    <div class="space-y-4">
      <div class="flex items-center gap-2">
        <Mail :size="16" class="text-text-muted" />
        <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.outputConfiguration }}</h3>
      </div>

      <!-- Email Recipients -->
      <div>
        <label for="email_recipients" class="mb-2 block text-sm font-medium text-text-primary">
          {{ strings.feeds.fields.emailRecipients }} <span class="text-text-muted">({{ strings.common.optional }})</span>
        </label>
        <input
          id="email_recipients"
          v-model="outputConfig.email_recipients"
          type="text"
          :placeholder="strings.feeds.placeholders.emailRecipients"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
        <p class="mt-2 text-xs text-text-muted">{{ strings.feeds.hints.commaSeparatedEmails }}</p>
      </div>

      <!-- Webhook URL -->
      <div>
        <label for="webhook_url" class="mb-2 block text-sm font-medium text-text-primary">
          {{ strings.feeds.fields.webhookUrl }} <span class="text-text-muted">({{ strings.common.optional }})</span>
        </label>
        <div class="relative">
          <Webhook class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
          <input
            id="webhook_url"
            v-model="outputConfig.webhook_url"
            type="url"
            :placeholder="strings.feeds.placeholders.webhookUrl"
            class="w-full rounded-lg border bg-bg-surface pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
            :class="
              errors?.['output_config.webhook_url']
                ? 'border-status-failed focus:ring-status-failed'
                : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
            "
          />
        </div>
        <Transition name="error">
          <p v-if="errors?.['output_config.webhook_url']" class="mt-2 text-sm text-status-failed">
            {{ errors['output_config.webhook_url'] }}
          </p>
        </Transition>
      </div>
    </div>

    <!-- Divider -->
    <div class="border-t border-border-subtle mt-8 mb-8" />

    <!-- Section 6: Auto-Export -->
    <div v-if="allDirectExportExporters && allDirectExportExporters.length > 0" class="space-y-4">
      <div class="flex items-center gap-2">
        <Download :size="16" class="text-text-muted" />
        <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.autoExport }}</h3>
        <a
          href="https://github.com/reconlyeu/reconly/blob/main/docs/guide/managing-feeds.md#output-configuration"
          target="_blank"
          rel="noopener noreferrer"
          class="ml-auto text-xs text-text-muted hover:text-accent-primary transition-colors inline-flex items-center gap-1"
        >
          Learn more
          <ExternalLink :size="11" />
        </a>
      </div>
      <p class="text-xs text-text-muted">
        {{ strings.feeds.autoExport.description }}
      </p>

      <!-- Warning for disabled exporters that were previously configured -->
      <div
        v-if="disabledConfiguredExporters.length > 0"
        class="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3"
      >
        <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
        <div class="text-xs text-amber-200">
          <p class="font-medium mb-1">{{ strings.feeds.autoExport.disabledExportersWarning }}</p>
          <ul class="list-disc list-inside">
            <li v-for="exp in disabledConfiguredExporters" :key="exp.name">
              {{ exp.name.charAt(0).toUpperCase() + exp.name.slice(1) }}
            </li>
          </ul>
          <p class="mt-1">{{ strings.feeds.autoExport.enableInSettings }} <span class="font-medium">{{ strings.feeds.autoExport.settingsExport }}</span> {{ strings.feeds.autoExport.toUseAgain }}</p>
        </div>
      </div>

      <!-- No enabled exporters message -->
      <div
        v-if="enabledExporters.length === 0"
        class="rounded-lg border border-border-subtle bg-bg-surface p-4 text-center"
      >
        <p class="text-sm text-text-muted">
          {{ strings.feeds.autoExport.noExportersEnabled }}
          <span class="font-medium text-text-secondary">{{ strings.feeds.autoExport.settingsExport }}</span>
          {{ strings.feeds.autoExport.toConfigureAutoExport }}
        </p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="exporter in enabledExporters"
          :key="exporter.name"
          class="rounded-lg border border-border-subtle bg-bg-surface p-4"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <input
                :id="`export-${exporter.name}`"
                type="checkbox"
                v-model="autoExportConfig[exporter.name].enabled"
                class="h-4 w-4 rounded border-border-default bg-bg-elevated text-accent-primary focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
              />
              <label :for="`export-${exporter.name}`" class="text-sm font-medium text-text-primary cursor-pointer">
                {{ exporter.name.charAt(0).toUpperCase() + exporter.name.slice(1) }}
              </label>
            </div>
            <span class="text-xs text-text-muted">.{{ exporter.file_extension }}</span>
          </div>
          <p class="text-xs text-text-muted mb-3">{{ exporter.description }}</p>

          <!-- Warning when enabled but no path configured -->
          <Transition name="slide">
            <div
              v-if="autoExportConfig[exporter.name]?.enabled && !hasPathConfigured(exporter.name)"
              class="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 mb-3"
            >
              <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
              <p class="text-xs text-amber-200">
                {{ strings.feeds.autoExport.noPathWarning }}
                <span class="font-medium">{{ strings.feeds.autoExport.settingsExport }}</span>.
              </p>
            </div>
          </Transition>

          <!-- Path override input (shown when enabled) -->
          <Transition name="slide">
            <div v-if="autoExportConfig[exporter.name]?.enabled" class="mt-3">
              <label :for="`export-path-${exporter.name}`" class="mb-1 block text-xs font-medium text-text-secondary">
                {{ strings.feeds.fields.customPath }}
                <span v-if="getGlobalExportPath(exporter.name)" class="text-text-muted">
                  ({{ strings.feeds.autoExport.leaveEmptyForGlobal }} <span class="font-mono text-text-secondary">{{ getGlobalExportPath(exporter.name) }}</span>)
                </span>
                <span v-else class="text-text-muted">({{ strings.feeds.autoExport.optionalOverride }})</span>
              </label>
              <input
                :id="`export-path-${exporter.name}`"
                v-model="autoExportConfig[exporter.name].path"
                type="text"
                :placeholder="getGlobalExportPath(exporter.name) ? strings.feeds.placeholders.overridePath : strings.feeds.placeholders.noGlobalPath"
                class="w-full rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
              />
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>
