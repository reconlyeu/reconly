<script setup lang="ts">
/**
 * Toast Provider - Custom styling for vue-toastification
 *
 * The toast plugin is registered globally in src/app.ts.
 * This component provides custom dark theme styling via global CSS.
 */
</script>

<template>
  <!-- This component provides global styles for toasts -->
  <div style="display: none;"></div>
</template>

<style>
/* Custom toast styling to match Skimberry dark theme */
:root {
  --toastify-color-light: #1a1a1a;
  --toastify-color-dark: #141414;
  --toastify-color-info: #4250af;
  --toastify-color-success: #18c249;
  --toastify-color-warning: #f59e0b;
  --toastify-color-error: #fa2921;
  --toastify-color-transparent: rgba(255, 255, 255, 0.7);

  --toastify-text-color-light: #e0e0e0;
  --toastify-text-color-dark: #e0e0e0;
}

.Vue-Toastification__toast {
  background-color: var(--bg-elevated, #141414) !important;
  color: var(--text-primary, #e0e0e0) !important;
  border: 1px solid var(--border-subtle, #2a2a2a) !important;
  border-radius: 0.5rem !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5) !important;
  font-family: 'Inter', sans-serif !important;
}

.Vue-Toastification__toast--success {
  border-left: 3px solid var(--accent-success, #18c249) !important;
}

.Vue-Toastification__toast--error {
  border-left: 3px solid var(--accent-error, #fa2921) !important;
}

.Vue-Toastification__toast--warning {
  border-left: 3px solid #f59e0b !important;
}

.Vue-Toastification__toast--info {
  border-left: 3px solid var(--accent-primary, #4250af) !important;
}

.Vue-Toastification__progress-bar {
  background: linear-gradient(90deg, var(--accent-primary, #4250af), var(--accent-success, #18c249)) !important;
}

.Vue-Toastification__close-button {
  color: var(--text-secondary, #a0a0a0) !important;
}

.Vue-Toastification__close-button:hover {
  color: var(--text-primary, #e0e0e0) !important;
}
</style>
