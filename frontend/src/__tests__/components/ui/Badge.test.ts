import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Badge from '@/components/ui/Badge.vue'

describe('Badge', () => {
  it('renders slot content', () => {
    const wrapper = mount(Badge, { slots: { default: 'Активна' } })
    expect(wrapper.text()).toBe('Активна')
  })

  it('renders active variant', () => {
    const wrapper = mount(Badge, { props: { variant: 'active' } })
    expect(wrapper.classes()).toContain('ui-badge--active')
  })

  it('renders inactive variant', () => {
    const wrapper = mount(Badge, { props: { variant: 'inactive' } })
    expect(wrapper.classes()).toContain('ui-badge--inactive')
  })

  it('renders success variant', () => {
    const wrapper = mount(Badge, { props: { variant: 'success' } })
    expect(wrapper.classes()).toContain('ui-badge--success')
  })

  it('renders warning variant', () => {
    const wrapper = mount(Badge, { props: { variant: 'warning' } })
    expect(wrapper.classes()).toContain('ui-badge--warning')
  })

  it('renders info variant', () => {
    const wrapper = mount(Badge, { props: { variant: 'info' } })
    expect(wrapper.classes()).toContain('ui-badge--info')
  })

  it('defaults to info variant', () => {
    const wrapper = mount(Badge)
    expect(wrapper.classes()).toContain('ui-badge--info')
  })

  it('renders as a span element', () => {
    const wrapper = mount(Badge)
    expect(wrapper.element.tagName).toBe('SPAN')
  })
})
