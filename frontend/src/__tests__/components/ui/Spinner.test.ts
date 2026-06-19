import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Spinner from '@/components/ui/Spinner.vue'

describe('Spinner', () => {
  it('renders an img element for cat', () => {
    const wrapper = mount(Spinner)
    expect(wrapper.find('img').exists()).toBe(true)
  })

  it('renders meditating pose by default', () => {
    const wrapper = mount(Spinner)
    const img = wrapper.find('img')
    expect(img.attributes('src')).toContain('meditating')
  })

  it('renders stretching pose when specified', () => {
    const wrapper = mount(Spinner, { props: { pose: 'stretching' } })
    const img = wrapper.find('img')
    expect(img.attributes('src')).toContain('stretching')
  })

  it('shows label text when provided', () => {
    const wrapper = mount(Spinner, { props: { label: 'Загрузка...' } })
    expect(wrapper.text()).toContain('Загрузка...')
  })

  it('does not render label element when not provided', () => {
    const wrapper = mount(Spinner)
    expect(wrapper.find('p').exists()).toBe(false)
  })

  it('has alt text on the cat image', () => {
    const wrapper = mount(Spinner)
    const img = wrapper.find('img')
    expect(img.attributes('alt')).toBeTruthy()
    expect(img.attributes('alt')).not.toBe('')
  })
})
