import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Button from '@/components/ui/Button.vue'

describe('Button', () => {
  it('renders primary variant by default', () => {
    const wrapper = mount(Button, { slots: { default: 'Click me' } })
    expect(wrapper.classes()).toContain('ui-btn--primary')
    expect(wrapper.text()).toBe('Click me')
  })

  it('renders secondary variant', () => {
    const wrapper = mount(Button, { props: { variant: 'secondary' } })
    expect(wrapper.classes()).toContain('ui-btn--secondary')
  })

  it('renders danger variant', () => {
    const wrapper = mount(Button, { props: { variant: 'danger' } })
    expect(wrapper.classes()).toContain('ui-btn--danger')
  })

  it('renders ghost variant', () => {
    const wrapper = mount(Button, { props: { variant: 'ghost' } })
    expect(wrapper.classes()).toContain('ui-btn--ghost')
  })

  it('renders sm size', () => {
    const wrapper = mount(Button, { props: { size: 'sm' } })
    expect(wrapper.classes()).toContain('ui-btn--sm')
  })

  it('renders lg size', () => {
    const wrapper = mount(Button, { props: { size: 'lg' } })
    expect(wrapper.classes()).toContain('ui-btn--lg')
  })

  it('is disabled when disabled prop is true', () => {
    const wrapper = mount(Button, { props: { disabled: true } })
    expect((wrapper.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('is disabled when loading prop is true', () => {
    const wrapper = mount(Button, { props: { loading: true } })
    expect((wrapper.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('is not disabled by default', () => {
    const wrapper = mount(Button)
    expect((wrapper.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('uses submit type when specified', () => {
    const wrapper = mount(Button, { props: { type: 'submit' } })
    expect(wrapper.attributes('type')).toBe('submit')
  })

  it('defaults to button type', () => {
    const wrapper = mount(Button)
    expect(wrapper.attributes('type')).toBe('button')
  })
})
