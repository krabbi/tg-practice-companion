import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BlessingsView from '@/views/BlessingsView.vue'

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

const BLESSING = {
  id: 'uuid-blessing-1',
  text: 'Have a wonderful day!',
  rotation_order: 1,
  active: true,
}

const BLESSING2 = {
  id: 'uuid-blessing-2',
  text: 'Stay positive!',
  rotation_order: 2,
  active: true,
}

describe('BlessingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('auth_token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders list of blessings on mount', async () => {
    stubFetch([BLESSING])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Have a wonderful day!')
    expect(wrapper.text()).toContain('Вкл')
  })

  it('shows empty hint when no blessings', async () => {
    stubFetch([])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Напутствия не найдены')
  })

  it('opens create modal on click', async () => {
    stubFetch([])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Добавить'))
    await addBtn!.trigger('click')

    expect(wrapper.text()).toContain('Новое напутствие')
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('validates empty text on submit', async () => {
    stubFetch([])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Добавить'))
    await addBtn!.trigger('click')
    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Текст обязателен')
  })

  it('shows up/down order controls for multiple blessings', async () => {
    stubFetch([BLESSING, BLESSING2])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    // btn-order buttons appear in both table and card list — find those in the table
    const tableOrderBtns = wrapper.find('table').findAll('button.btn-order')
    expect(tableOrderBtns.length).toBe(4)
    expect((tableOrderBtns[0].element as HTMLButtonElement).disabled).toBe(true)
    expect((tableOrderBtns[3].element as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows inactive row style for inactive blessing', async () => {
    stubFetch([{ ...BLESSING, active: false }])
    const wrapper = mount(BlessingsView)
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows[0].classes()).toContain('inactive')
    expect(wrapper.text()).toContain('Выкл')
  })
})
