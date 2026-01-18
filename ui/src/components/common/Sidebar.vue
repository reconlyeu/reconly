<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue';
import {
  LayoutDashboard,
  FileText,
  Rss,
  ListTree,
  History,
  FileCode,
  BarChart3,
  Network,
  MessageSquare,
  Settings,
  LogOut,
  FlaskConical,
  type LucideIcon,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import { useAuthStore } from '@/stores/auth';
import { useDemoStore } from '@/stores/demo';

interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
}

const props = defineProps<{
  currentPath: string;
}>();

// Store references - initialized in onMounted to ensure Pinia is available
const authStore = shallowRef<ReturnType<typeof useAuthStore> | null>(null);
const demoStore = shallowRef<ReturnType<typeof useDemoStore> | null>(null);
const showLogout = ref(false);

// Check auth config and demo mode on mount
onMounted(async () => {
  // Access stores inside onMounted to ensure Pinia is initialized
  authStore.value = useAuthStore();
  demoStore.value = useDemoStore();
  await authStore.value.checkAuthConfig();
  await demoStore.value.fetchDemoMode();
  showLogout.value = authStore.value.authRequired;
});

const handleLogout = async () => {
  await authStore.value?.logout();
};

const navItems: NavItem[] = [
  { name: strings.nav.dashboard, href: '/', icon: LayoutDashboard },
  { name: strings.nav.digests, href: '/digests', icon: FileText },
  { name: strings.nav.feeds, href: '/feeds', icon: ListTree },
  { name: strings.nav.sources, href: '/sources', icon: Rss },
  { name: strings.nav.templates, href: '/templates', icon: FileCode },
  { name: strings.nav.chat, href: '/chat', icon: MessageSquare },
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

      <!-- Logout Button (shown when auth is required) -->
      <button
        v-if="showLogout"
        @click="handleLogout"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium text-text-secondary hover:text-status-failed hover:bg-status-failed/10 transition-colors"
      >
        <LogOut class="w-[1.35rem] h-[1.35rem] flex-shrink-0" />
        <span>Logout</span>
      </button>
    </nav>

    <!-- Footer - height matches the fixed quick actions bar (h-14 = 56px) -->
    <div class="h-14 px-4 border-t border-border-subtle flex items-center justify-center gap-3">
      <!-- Demo Mode Indicator -->
      <div
        v-if="demoStore?.isDemoMode"
        class="flex items-center gap-1.5 text-xs text-amber-500/70"
      >
        <FlaskConical class="w-3.5 h-3.5" />
        <span>Demo Mode</span>
      </div>

      <div class="text-xs text-text-muted">
        {{ strings.app.tagline }}
      </div>
    </div>
  </aside>
</template>
