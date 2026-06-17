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
  min-height: 100vh;
}

.nav {
  display: flex;
  overflow-x: auto;
  background-color: var(--tg-theme-secondary-bg-color, #f0f0f0);
  padding: 0.5rem;
  gap: 0.25rem;
  flex-shrink: 0;
}

.nav-link {
  text-decoration: none;
  color: var(--tg-theme-hint-color, #666);
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  white-space: nowrap;
  transition: background-color 0.15s;
}

.nav-link:hover {
  background-color: var(--tg-theme-bg-color, #e0e0e0);
}

.nav-link.active {
  color: var(--tg-theme-link-color, #2481cc);
  font-weight: 600;
  background-color: var(--tg-theme-bg-color, #ffffff);
}

.content {
  flex: 1;
  padding: 1rem;
}
</style>
