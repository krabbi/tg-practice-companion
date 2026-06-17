import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PracticesView from '@/views/PracticesView.vue'

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

describe('PracticesView cadence form switch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('auth_token', 'test-token')
    stubFetch([])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    localStorage.clear()
  })

  async function openForm() {
    const wrapper = mount(PracticesView, {
      global: { plugins: [] },
    })
    await flushPromises()
    await wrapper.find('button.btn-primary').trigger('click')
    return wrapper
  }

  it('shows interval_hours field when periodicity_type is every_n_hours', async () => {
    const wrapper = await openForm()

    const selects = wrapper.findAll('select')
    const periodicitySelect = selects.find((s) =>
      s.findAll('option').some((o) => o.element.value === 'every_n_hours'),
    )
    expect(periodicitySelect).toBeDefined()

    await periodicitySelect!.setValue('every_n_hours')

    expect(wrapper.find('input[type="number"][min="1"]').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="06:00"]').exists()).toBe(false)
  })

  it('shows HH:MM time editor when periodicity_type is fixed_times', async () => {
    const wrapper = await openForm()

    const selects = wrapper.findAll('select')
    const periodicitySelect = selects.find((s) =>
      s.findAll('option').some((o) => o.element.value === 'fixed_times'),
    )
    expect(periodicitySelect).toBeDefined()

    await periodicitySelect!.setValue('fixed_times')

    expect(wrapper.text()).toContain('Добавить')
    expect(wrapper.find('input[placeholder="06:00"]').exists()).toBe(true)
  })
})
