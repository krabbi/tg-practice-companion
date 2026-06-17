import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WantsView from '@/views/WantsView.vue'

const { mockLogout, mockRouterPush } = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockRouterPush: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({ logout: mockLogout })),
}))

vi.mock('@/router', () => ({
  default: { push: mockRouterPush },
}))

function stubFetch(body: unknown, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  )
}

const WANT = {
  id: 'uuid-want-1',
  user_id: 1,
  text: 'Learn piano',
  done: false,
  created_at: '2024-01-01T00:00:00',
}

describe('WantsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('auth_token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders list of wants on mount', async () => {
    stubFetch([WANT])
    const wrapper = mount(WantsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Learn piano')
    expect(wrapper.text()).toContain('Не выполнено')
  })

  it('shows empty hint when no wants', async () => {
    stubFetch([])
    const wrapper = mount(WantsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Список пуст')
  })

  it('opens create modal on click', async () => {
    stubFetch([])
    const wrapper = mount(WantsView)
    await flushPromises()

    await wrapper.find('button.btn-primary').trigger('click')

    expect(wrapper.text()).toContain('Новое желание')
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('validates empty text on submit', async () => {
    stubFetch([])
    const wrapper = mount(WantsView)
    await flushPromises()

    await wrapper.find('button.btn-primary').trigger('click')
    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Текст обязателен')
  })

  it('shows done status when want is done', async () => {
    stubFetch([{ ...WANT, done: true }])
    const wrapper = mount(WantsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Выполнено')
  })
})
