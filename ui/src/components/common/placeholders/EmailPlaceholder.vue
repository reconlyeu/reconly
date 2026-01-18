<script setup lang="ts">
/**
 * Placeholder SVG for Email/IMAP digests when no preview image is available.
 * Displays a stylized envelope icon with blue accent colors.
 */
</script>

<template>
  <svg
    viewBox="0 0 96 54"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="w-full h-full"
    preserveAspectRatio="xMidYMid slice"
  >
    <!-- Background with gradient -->
    <defs>
      <linearGradient id="email-bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#1a1a2e" />
        <stop offset="100%" stop-color="#16162a" />
      </linearGradient>
      <linearGradient id="email-icon" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#0ea5e9" stop-opacity="0.8" />
        <stop offset="100%" stop-color="#0284c7" stop-opacity="0.8" />
      </linearGradient>
    </defs>

    <!-- Base rectangle - 16:9 aspect ratio -->
    <rect width="96" height="54" fill="url(#email-bg)" />

    <!-- Email envelope icon - centered -->
    <g transform="translate(23, 7)">
      <!-- Envelope body -->
      <rect
        x="0"
        y="8"
        width="50"
        height="32"
        rx="4"
        fill="url(#email-icon)"
      />

      <!-- Envelope flap (top triangle shape) -->
      <path
        d="M0 12 L25 28 L50 12 L50 8 Q50 4 46 4 L4 4 Q0 4 0 8 Z"
        fill="url(#email-icon)"
      />

      <!-- Inner fold line (darker) -->
      <path
        d="M2 10 L25 26 L48 10"
        stroke="#1a1a2e"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        fill="none"
      />

      <!-- Highlight lines on envelope body -->
      <line x1="8" y1="32" x2="20" y2="32" stroke="#1a1a2e" stroke-width="2" stroke-linecap="round" opacity="0.5" />
      <line x1="8" y1="36" x2="16" y2="36" stroke="#1a1a2e" stroke-width="2" stroke-linecap="round" opacity="0.5" />
    </g>
  </svg>
</template>
