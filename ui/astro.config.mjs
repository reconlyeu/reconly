// @ts-check
import { defineConfig } from 'astro/config';
import vue from '@astrojs/vue';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Edition: 'oss' (default) or 'enterprise'
// Set via VITE_EDITION environment variable
const edition = process.env.VITE_EDITION || 'oss';

// https://astro.build/config
export default defineConfig({
  integrations: [
    vue({
      appEntrypoint: '/src/app.ts',
    }),
  ],

  vite: {
    plugins: [tailwindcss()],
    define: {
      // Make edition available at build time
      'import.meta.env.VITE_EDITION': JSON.stringify(edition),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@components': path.resolve(__dirname, './src/components'),
        '@config': path.resolve(__dirname, './src/config'),
        '@layouts': path.resolve(__dirname, './src/layouts'),
        '@stores': path.resolve(__dirname, './src/stores'),
        '@services': path.resolve(__dirname, './src/services'),
        '@types': path.resolve(__dirname, './src/types'),
        '@i18n': path.resolve(__dirname, './src/i18n'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  },

  // Output static files for serving via FastAPI
  output: 'static',

  // Build output directory
  outDir: './dist',

  // Base path (can be configured for subdirectory deployment)
  base: '/',

  // Dev server configuration
  server: {
    port: 4321,
    host: true,
  },
});
