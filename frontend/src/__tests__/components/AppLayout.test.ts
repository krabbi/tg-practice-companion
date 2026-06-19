import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import AppLayout from '@/components/AppLayout.vue'

vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ path: '/practices' })),
}))

const RouterLink = defineComponent({
  name: 'RouterLink',
  props: ['to'],
  template: '<a :href="to" class="nav-link"><slot /></a>',
})

const RouterView = defineComponent({
  name: 'RouterView',
  template: '<div class="router-view" />',
})

const globalStubs = {
  RouterLink,
  RouterView,
}

describe('AppLayout', () => {
  it('renders the nav element with all navigation links', () => {
    const wrapper = mount(AppLayout, { global: { stubs: globalStubs } })
    const nav = wrapper.find('nav.nav')
    expect(nav.exists()).toBe(true)
    const links = wrapper.findAll('a')
    const labels = links.map((l) => l.text())
    expect(labels).toContain('Практики')
    expect(labels).toContain('Медиа')
    expect(labels).toContain('Дневник')
    expect(labels).toContain('Отчёты')
    expect(labels).toContain('Хочу')
    expect(labels).toContain('Напутствия')
  })

  it('renders the main content area', () => {
    const wrapper = mount(AppLayout, { global: { stubs: globalStubs } })
    expect(wrapper.find('main.content').exists()).toBe(true)
  })
})
