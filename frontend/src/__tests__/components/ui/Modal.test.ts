import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Modal from '@/components/ui/Modal.vue'

const stubs = { teleport: true }

describe('Modal', () => {
  it('renders nothing when open is false', () => {
    const wrapper = mount(Modal, {
      props: { open: false },
      global: { stubs },
    })
    expect(wrapper.find('.ui-modal-overlay').exists()).toBe(false)
  })

  it('renders overlay when open is true', () => {
    const wrapper = mount(Modal, {
      props: { open: true },
      global: { stubs },
    })
    expect(wrapper.find('.ui-modal-overlay').exists()).toBe(true)
  })

  it('shows title when title prop is provided', () => {
    const wrapper = mount(Modal, {
      props: { open: true, title: 'Заголовок' },
      global: { stubs },
    })
    expect(wrapper.find('.ui-modal__title').text()).toBe('Заголовок')
  })

  it('renders slot content', () => {
    const wrapper = mount(Modal, {
      props: { open: true },
      slots: { default: '<p class="modal-content">Содержимое</p>' },
      global: { stubs },
    })
    expect(wrapper.find('.modal-content').exists()).toBe(true)
    expect(wrapper.find('.modal-content').text()).toBe('Содержимое')
  })

  it('emits close when overlay is clicked', async () => {
    const wrapper = mount(Modal, {
      props: { open: true },
      global: { stubs },
    })
    await wrapper.find('.ui-modal-overlay').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close when close button is clicked', async () => {
    const wrapper = mount(Modal, {
      props: { open: true, title: 'Test' },
      global: { stubs },
    })
    await wrapper.find('.ui-modal__close').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('has role="dialog" on modal element', () => {
    const wrapper = mount(Modal, {
      props: { open: true, title: 'Диалог' },
      global: { stubs },
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })
})
