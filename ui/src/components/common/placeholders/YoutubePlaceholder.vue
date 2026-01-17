<script setup lang="ts">
/**
 * Placeholder SVG for YouTube digests when no preview image is available.
 * Displays a stylized video player with play button.
 */
</script>

<template>
  <svg
    viewBox="0 0 96 68"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="w-full h-full"
    preserveAspectRatio="xMidYMid slice"
  >
    <!-- Background with gradient -->
    <defs>
      <linearGradient id="youtube-bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#1a1a2e" />
        <stop offset="100%" stop-color="#16162a" />
      </linearGradient>
      <linearGradient id="youtube-red" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#b91c1c" />
        <stop offset="100%" stop-color="#991b1b" />
      </linearGradient>
    </defs>

    <!-- Base rectangle -->
    <rect width="96" height="68" rx="4" fill="url(#youtube-bg)" />

    <!-- YouTube-style play button (red rounded rectangle with play icon) -->
    <rect x="28" y="19" width="40" height="28" rx="8" fill="url(#youtube-red)" opacity="0.85" />

    <!-- Play triangle -->
    <path d="M43 26 L43 40 L55 33 Z" fill="white" />
  </svg>
</template>
