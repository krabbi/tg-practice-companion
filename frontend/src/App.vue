<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Spinner from '@/components/ui/Spinner.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

type AppState = 'loading' | 'error' | 'ready'

const appState = ref<AppState>('loading')
const errorMessage = ref('')
const authStore = useAuthStore()
const router = useRouter()

onMounted(async () => {
  window.Telegram?.WebApp?.ready()
  window.Telegram?.WebApp?.expand()

  if (authStore.isAuthenticated) {
    appState.value = 'ready'
    return
  }

  const initData = window.Telegram?.WebApp?.initData
  if (!initData) {
    appState.value = 'error'
    errorMessage.value = 'Откройте приложение через кнопку в Telegram-боте.'
    return
  }

  try {
    await authStore.login(initData)
    appState.value = 'ready'
    await router.push('/practices')
  } catch {
    appState.value = 'error'
    errorMessage.value = 'Не удалось выполнить вход. Попробуйте открыть приложение снова.'
  }
})
</script>

<template>
  <div v-if="appState === 'loading'" class="app-loading">
    <Spinner pose="meditating" label="Загрузка..." />
  </div>
  <div v-else-if="appState === 'error'" class="app-error">
    <EmptyState pose="lounging" label="Ошибка доступа" />
    <p class="app-error__msg">{{ errorMessage }}</p>
  </div>
  <router-view v-else />
</template>

<style>
@import './styles/tokens.css';

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-family);
  background-color: var(--color-bg);
  color: var(--color-text);
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}

/* shared view wrapper */
.view {
  max-width: var(--container-max);
  margin: 0 auto;
}

/* shared view header */
.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.view-header h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.02em;
}

/* shared error banner */
.error-banner {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
}

/* shared success banner */
.success-banner {
  color: var(--color-success);
  background: var(--color-success-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
}

/* shared card list (mobile) */
.card-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* shared table wrap (wide screens only) */
.table-wrap {
  overflow-x: auto;
}

/* hide card list on wide, hide table on narrow */
@media (min-width: 481px) {
  .card-list { display: none !important; }
}

@media (max-width: 480px) {
  .table-wrap table { display: none; }
}
</style>

<style scoped>
.app-loading,
.app-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  padding: var(--space-8);
  text-align: center;
  gap: var(--space-3);
}

.app-error__msg {
  font-size: var(--text-base);
  color: var(--color-hint);
  max-width: 280px;
}
</style>
