import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { postTelegramAuth } from '@/api/auth'

const TOKEN_KEY = 'auth_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))

  const isAuthenticated = computed(() => token.value !== null)

  async function login(initData: string): Promise<void> {
    const response = await postTelegramAuth(initData)
    token.value = response.token
    localStorage.setItem(TOKEN_KEY, response.token)
  }

  function logout(): void {
    token.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, isAuthenticated, login, logout }
})
