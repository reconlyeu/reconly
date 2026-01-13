<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  LayoutDashboard,
  FileText,
  Rss,
  ListTree,
  History,
  FileCode,
  BarChart3,
  Network,
  Settings,
  LogOut,
  type LucideIcon,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import { useAuthStore } from '@/stores/auth';

interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
}

const props = defineProps<{
  currentPath: string;
}>();

const authStore = useAuthStore();
const showLogout = ref(false);

// Check auth config on mount
onMounted(async () => {
  await authStore.checkAuthConfig();
  showLogout.value = authStore.authRequired;
});

const handleLogout = async () => {
  await authStore.logout();
};

const navItems: NavItem[] = [
  { name: strings.nav.dashboard, href: '/', icon: LayoutDashboard },
  { name: strings.nav.digests, href: '/digests', icon: FileText },
  { name: strings.nav.feeds, href: '/feeds', icon: ListTree },
  { name: strings.nav.sources, href: '/sources', icon: Rss },
  { name: strings.nav.templates, href: '/templates', icon: FileCode },
  { name: strings.nav.analytics, href: '/analytics', icon: BarChart3 },
  { name: strings.nav.knowledgeGraph, href: '/knowledge-graph', icon: Network },
  { name: strings.nav.feedRuns, href: '/feed-runs', icon: History },
  { name: strings.nav.settings, href: '/settings', icon: Settings },
];

const isActive = (href: string) => {
  if (href === '/') {
    return props.currentPath === '/';
  }
  return props.currentPath.startsWith(href);
};
</script>

<template>
  <aside
    class="fixed inset-y-0 left-0 z-50 w-64 bg-bg-surface border-r border-border-subtle flex flex-col"
  >
    <!-- Logo -->
    <div class="h-16 flex items-center pl-[18px] border-b border-border-subtle">
      <a href="/" class="flex items-center gap-3 group">
        <div class="w-10 h-10 flex items-center justify-center">
          <img src="/reconly-logo.png" alt="reconly" class="w-full h-full object-contain" />
        </div>
        <span class="text-xl font-semibold text-text-primary group-hover:text-accent-primary transition-colors">
          {{ strings.app.name }}
        </span>
      </a>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
      <a
        v-for="item in navItems"
        :key="item.href"
        :href="item.href"
        :class="[
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium transition-colors',
          isActive(item.href)
            ? 'bg-accent-primary text-white'
            : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover',
        ]"
      >
        <component :is="item.icon" class="w-[1.35rem] h-[1.35rem] flex-shrink-0" />
        <span>{{ item.name }}</span>
      </a>
    </nav>

    <!-- Footer -->
    <div class="p-4 border-t border-border-subtle space-y-3">
      <!-- Logout Button (shown when auth is required) -->
      <button
        v-if="showLogout"
        @click="handleLogout"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-text-secondary hover:text-status-failed hover:bg-status-failed/10 transition-colors"
      >
        <LogOut class="w-5 h-5 flex-shrink-0" />
        <span>Logout</span>
      </button>

      <div class="text-xs text-text-muted text-center">
        {{ strings.app.tagline }}
      </div>
    </div>
  </aside>
</template>
