<script setup lang="ts">
/**
 * Placeholder SVG for RSS/Article digests when no preview image is available.
 * Displays a stylized RSS feed icon with muted accent colors.
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
      <linearGradient id="rss-bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#1a1a2e" />
        <stop offset="100%" stop-color="#16162a" />
      </linearGradient>
      <linearGradient id="rss-icon" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#c2410c" stop-opacity="0.7" />
        <stop offset="100%" stop-color="#9a3412" stop-opacity="0.7" />
      </linearGradient>
    </defs>

    <!-- Base rectangle - 16:9 aspect ratio -->
    <rect width="96" height="54" fill="url(#rss-bg)" />

    <!-- RSS Icon - centered and sized to fill -->
    <g transform="translate(24, 3)">
      <!-- Rounded square background -->
      <rect width="48" height="48" rx="8" fill="url(#rss-icon)" />

      <!-- RSS dot -->
      <circle cx="14" cy="38" r="5" fill="#1a1a2e" />

      <!-- Inner arc -->
      <path
        d="M9 26 A17 17 0 0 1 26 43"
        stroke="#1a1a2e"
        stroke-width="5"
        stroke-linecap="round"
        fill="none"
      />

      <!-- Outer arc -->
      <path
        d="M9 14 A29 29 0 0 1 38 43"
        stroke="#1a1a2e"
        stroke-width="5"
        stroke-linecap="round"
        fill="none"
      />
    </g>
  </svg>
</template>
