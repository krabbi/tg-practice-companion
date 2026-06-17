import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ApiError } from '@/api/client'
import ReportsView from '@/views/ReportsView.vue'

const { mockGetPeriodReport } = vi.hoisted(() => ({
  mockGetPeriodReport: vi.fn(),
}))

vi.mock('@/api/reports', () => ({
  getPeriodReport: mockGetPeriodReport,
}))

const REPORT = {
  date_from: '2024-01-01',
  date_to: '2024-01-31',
  n_total: 42,
  n_leads: 30,
  n_practices: 100,
  n_good_deeds: 5,
}

describe('ReportsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the date range form', () => {
    const wrapper = mount(ReportsView)

    expect(wrapper.findAll('input[type="date"]').length).toBe(2)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('shows validation error when date_from is missing', async () => {
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Укажите дату начала')
    expect(mockGetPeriodReport).not.toHaveBeenCalled()
  })

  it('shows validation error when date_to is missing', async () => {
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')

    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('Укажите дату окончания')
    expect(mockGetPeriodReport).not.toHaveBeenCalled()
  })

  it('shows validation error when date_to is before date_from', async () => {
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-31')
    await dateInputs[1].setValue('2024-01-01')

    await wrapper.find('form').trigger('submit')

    expect(wrapper.text()).toContain('не раньше')
    expect(mockGetPeriodReport).not.toHaveBeenCalled()
  })

  it('calls getPeriodReport with correct dates on submit', async () => {
    mockGetPeriodReport.mockResolvedValueOnce(REPORT)
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockGetPeriodReport).toHaveBeenCalledWith('2024-01-01', '2024-01-31')
  })

  it('renders report statistics after successful fetch', async () => {
    mockGetPeriodReport.mockResolvedValueOnce(REPORT)
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('30')
    expect(wrapper.text()).toContain('100')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('71%')
  })

  it('shows — for leads percent when n_total is 0', async () => {
    mockGetPeriodReport.mockResolvedValueOnce({ ...REPORT, n_total: 0, n_leads: 0 })
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const resultsSection = wrapper.find('.report-results')
    expect(resultsSection.text()).toContain('—')
  })

  it('shows error message when fetch fails', async () => {
    mockGetPeriodReport.mockRejectedValueOnce(new ApiError(500, 'Server error', 'DB down'))
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('DB down')
  })

  it('shows period heading in results', async () => {
    mockGetPeriodReport.mockResolvedValueOnce(REPORT)
    const wrapper = mount(ReportsView)

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('2024-01-01')
    expect(wrapper.text()).toContain('2024-01-31')
  })
})
