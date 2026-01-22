<script setup lang="ts">
/**
 * Placeholder SVG for AI Agent research digests when no preview image is available.
 * Displays a globe with grid lines and a friendly robot face peeking from the bottom.
 * Style matches other placeholder icons (ArticlePlaceholder, YoutubePlaceholder).
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
    <!-- Background with gradient (matches other placeholders) -->
    <defs>
      <linearGradient id="agent-bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#1a1a2e" />
        <stop offset="100%" stop-color="#16162a" />
      </linearGradient>
      <linearGradient id="agent-accent" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#7c3aed" stop-opacity="0.7" />
        <stop offset="100%" stop-color="#5b21b6" stop-opacity="0.7" />
      </linearGradient>
    </defs>

    <!-- Base rectangle -->
    <rect width="96" height="54" fill="url(#agent-bg)" />

    <!-- Globe with robot - centered -->
    <g transform="translate(24, 3)">
      <!-- Globe circle background -->
      <circle cx="24" cy="24" r="23" fill="url(#agent-accent)" />

      <!-- Globe grid lines (matching reference) -->
      <!-- Outer ellipse arcs (curved longitude lines) -->
      <ellipse cx="24" cy="24" rx="8" ry="23" stroke="#1a1a2e" stroke-width="1.5" fill="none" />
      <ellipse cx="24" cy="24" rx="16" ry="23" stroke="#1a1a2e" stroke-width="1.5" fill="none" />

      <!-- Horizontal latitude lines -->
      <ellipse cx="24" cy="10" rx="21" ry="5" stroke="#1a1a2e" stroke-width="1.5" fill="none" />
      <line x1="1" y1="24" x2="47" y2="24" stroke="#1a1a2e" stroke-width="1.5" />
      <ellipse cx="24" cy="38" rx="21" ry="5" stroke="#1a1a2e" stroke-width="1.5" fill="none" />

      <!-- Vertical center line -->
      <line x1="24" y1="1" x2="24" y2="47" stroke="#1a1a2e" stroke-width="1.5" />

      <!-- Robot face (peeking from bottom, rounded head shape) -->
      <path
        d="M10 42 Q10 32 24 32 Q38 32 38 42 Q38 48 24 48 Q10 48 10 42 Z"
        fill="#c4b5fd"
      />

      <!-- Robot antenna (dot on top of head) -->
      <circle cx="24" cy="26" r="2.5" fill="#c4b5fd" />

      <!-- Robot eyes (two simple dots) -->
      <circle cx="18" cy="40" r="2.5" fill="#1a1a2e" />
      <circle cx="30" cy="40" r="2.5" fill="#1a1a2e" />
    </g>
  </svg>
</template>
