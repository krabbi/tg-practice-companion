import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from '@/components/ui/EmptyState.vue'

describe('EmptyState', () => {
  it('renders label text', () => {
    const wrapper = mount(EmptyState, { props: { label: 'Нет данных' } })
    expect(wrapper.text()).toContain('Нет данных')
  })

  it('renders an img element for cat', () => {
    const wrapper = mount(EmptyState, { props: { pose: 'lounging' } })
    expect(wrapper.find('img').exists()).toBe(true)
  })

  it('has meaningful alt text for lounging pose', () => {
    const wrapper = mount(EmptyState, { props: { pose: 'lounging' } })
    const img = wrapper.find('img')
    expect(img.attributes('alt')).toBeTruthy()
    expect(img.attributes('alt')).not.toBe('')
  })

  it('has meaningful alt text for meditating pose', () => {
    const wrapper = mount(EmptyState, { props: { pose: 'meditating' } })
    const img = wrapper.find('img')
    expect(img.attributes('alt')).toBeTruthy()
  })

  it('has meaningful alt text for yoga pose', () => {
    const wrapper = mount(EmptyState, { props: { pose: 'yoga' } })
    const img = wrapper.find('img')
    expect(img.attributes('alt')).toBeTruthy()
  })

  it('has meaningful alt text for stretching pose', () => {
    const wrapper = mount(EmptyState, { props: { pose: 'stretching' } })
    const img = wrapper.find('img')
    expect(img.attributes('alt')).toBeTruthy()
  })

  it('renders slot content', () => {
    const wrapper = mount(EmptyState, {
      props: { label: 'Пусто' },
      slots: { default: '<button>Создать</button>' },
    })
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('does not render label p when label is not provided', () => {
    const wrapper = mount(EmptyState)
    expect(wrapper.find('p').exists()).toBe(false)
  })

  it('defaults to lounging pose (renders img)', () => {
    const wrapper = mount(EmptyState)
    expect(wrapper.find('img').exists()).toBe(true)
  })
})
