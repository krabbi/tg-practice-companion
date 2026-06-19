<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentPath = computed(() => route.path)

const navItems = [
  { path: '/practices', label: 'Практики' },
  { path: '/media', label: 'Медиа' },
  { path: '/journal', label: 'Дневник' },
  { path: '/reports', label: 'Отчёты' },
  { path: '/wants', label: 'Хочу' },
  { path: '/blessings', label: 'Напутствия' },
]
</script>

<template>
  <div class="layout">
    <nav class="nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :class="['nav-link', { active: currentPath === item.path }]"
      >
        {{ item.label }}
      </router-link>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
}

.nav {
  display: flex;
  overflow-x: auto;
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--glass-border);
  padding: var(--space-2);
  padding-top: calc(var(--space-2) + var(--tg-safe-area-inset-top, env(safe-area-inset-top, 0px)));
  gap: var(--space-1);
  flex-shrink: 0;
  /* hide scrollbar but keep scroll functional */
  scrollbar-width: none;
}

.nav::-webkit-scrollbar {
  display: none;
}

.nav-link {
  text-decoration: none;
  color: var(--color-hint);
  padding: 0 var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  transition: background-color var(--transition-fast) ease, color var(--transition-fast) ease;
  display: flex;
  align-items: center;
  min-height: var(--tap-target);
}

.nav-link:hover {
  background-color: color-mix(in srgb, var(--color-hint) 12%, transparent);
}

.nav-link.active {
  color: var(--color-accent);
  font-weight: var(--font-weight-semibold);
  background-color: var(--color-bg);
}

.content {
  flex: 1;
  padding: var(--space-4);
}
</style>
