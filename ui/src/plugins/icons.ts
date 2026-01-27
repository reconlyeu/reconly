/**
 * Iconify icon bundle registration.
 *
 * This file imports and registers icon collections for offline use.
 * Icons are bundled at build time instead of fetched from CDN.
 *
 * Used icon sets:
 * - mdi: Material Design Icons (rss, email, web, youtube, robot, etc.)
 * - simple-icons: Brand logos (ollama, openai, anthropic, etc.)
 */
import { addCollection } from '@iconify/vue';

// Import icon collections
import mdiIcons from '@iconify-json/mdi/icons.json';
import simpleIcons from '@iconify-json/simple-icons/icons.json';

/**
 * Register all bundled icon collections.
 * Call this once at app initialization.
 */
export function registerIcons(): void {
  // Register Material Design Icons
  addCollection(mdiIcons);

  // Register Simple Icons (brand logos)
  addCollection(simpleIcons);
}
