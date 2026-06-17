<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
    <p>Загрузка...</p>
  </div>
  <div v-else-if="appState === 'error'" class="app-error">
    <h2>Ошибка доступа</h2>
    <p>{{ errorMessage }}</p>
  </div>
  <router-view v-else />
</template>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--tg-theme-bg-color, #ffffff);
  color: var(--tg-theme-text-color, #000000);
  min-height: 100vh;
}

.app-loading,
.app-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  text-align: center;
  gap: 1rem;
}

.app-error h2 {
  font-size: 1.5rem;
}
</style>
