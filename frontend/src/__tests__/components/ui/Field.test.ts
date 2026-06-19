import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Field from '@/components/ui/Field.vue'

describe('Field', () => {
  it('renders label when provided', () => {
    const wrapper = mount(Field, { props: { label: 'Текст *' } })
    expect(wrapper.find('label').exists()).toBe(true)
    expect(wrapper.find('label').text()).toBe('Текст *')
  })

  it('does not render label when not provided', () => {
    const wrapper = mount(Field)
    expect(wrapper.find('label').exists()).toBe(false)
  })

  it('shows error message when error prop is provided', () => {
    const wrapper = mount(Field, { props: { error: 'Поле обязательно' } })
    const err = wrapper.find('.ui-field__error')
    expect(err.exists()).toBe(true)
    expect(err.text()).toBe('Поле обязательно')
  })

  it('does not show hint when error is provided', () => {
    const wrapper = mount(Field, { props: { error: 'Ошибка', hint: 'Подсказка' } })
    expect(wrapper.find('.ui-field__hint').exists()).toBe(false)
    expect(wrapper.find('.ui-field__error').exists()).toBe(true)
  })

  it('shows hint when no error is provided', () => {
    const wrapper = mount(Field, { props: { hint: 'Подсказка' } })
    const hint = wrapper.find('.ui-field__hint')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toBe('Подсказка')
  })

  it('does not show error or hint when neither is provided', () => {
    const wrapper = mount(Field)
    expect(wrapper.find('.ui-field__error').exists()).toBe(false)
    expect(wrapper.find('.ui-field__hint').exists()).toBe(false)
  })

  it('renders slot content', () => {
    const wrapper = mount(Field, {
      slots: { default: '<input type="text" />' },
    })
    expect(wrapper.find('input').exists()).toBe(true)
  })
})
