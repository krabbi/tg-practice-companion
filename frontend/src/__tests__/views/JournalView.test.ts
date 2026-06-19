import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ApiError } from '@/api/client'
import JournalView from '@/views/JournalView.vue'
import type { JournalEntry, JournalListResponse } from '@/api/journal'

const { mockListJournal, mockListPractices } = vi.hoisted(() => ({
  mockListJournal: vi.fn(),
  mockListPractices: vi.fn(),
}))

vi.mock('@/api/journal', () => ({
  listJournal: mockListJournal,
  getJournalEntry: vi.fn(),
}))

vi.mock('@/api/practices', () => ({
  listPractices: mockListPractices,
}))

const PRACTICE = { id: 'prac-1', name: 'Morning question' }

const ENTRY: JournalEntry = {
  id: 'entry-1',
  text: 'This is a test entry with some content',
  source: 'text',
  created_at: '2024-01-15T09:30:00',
  practice_id: 'prac-1',
  practice_name: 'Morning question',
  self_assessment: { leads_to_goals: true, set_via: 'user' },
}

const VOICE_ENTRY: JournalEntry = {
  id: 'entry-2',
  text: 'Voice entry content',
  source: 'voice',
  created_at: '2024-01-16T10:00:00',
  practice_id: null,
  practice_name: null,
  self_assessment: { leads_to_goals: false, set_via: 'user' },
}

function makeListResponse(items: JournalEntry[], total?: number): JournalListResponse {
  return { items, total: total ?? items.length, page: 1, page_size: 20 }
}

describe('JournalView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockListJournal.mockResolvedValue(makeListResponse([]))
    mockListPractices.mockResolvedValue([PRACTICE])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('calls listJournal on mount and shows empty state', async () => {
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(mockListJournal).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Записей не найдено')
  })

  it('renders entries in the table', async () => {
    mockListJournal.mockResolvedValueOnce(makeListResponse([ENTRY]))
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(wrapper.text()).toContain('Morning question')
    expect(wrapper.text()).toContain('Текст')
    expect(wrapper.text()).toContain('✅')
  })

  it('renders voice source correctly', async () => {
    mockListJournal.mockResolvedValueOnce(makeListResponse([VOICE_ENTRY]))
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(wrapper.text()).toContain('Голос')
    expect(wrapper.text()).toContain('❌')
  })

  it('shows no assessment dash when self_assessment is null', async () => {
    const entry: JournalEntry = { ...ENTRY, self_assessment: null }
    mockListJournal.mockResolvedValueOnce(makeListResponse([entry]))
    const wrapper = mount(JournalView)
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows[0].text()).toContain('—')
  })

  it('populates practice dropdown from listPractices', async () => {
    const wrapper = mount(JournalView)
    await flushPromises()

    const select = wrapper.find('select')
    expect(select.text()).toContain('Morning question')
  })

  it('opens detail modal when row is clicked', async () => {
    mockListJournal.mockResolvedValueOnce(makeListResponse([ENTRY]))
    const wrapper = mount(JournalView)
    await flushPromises()

    const row = wrapper.find('tbody tr.clickable-row')
    await row.trigger('click')

    expect(wrapper.find('.modal').exists()).toBe(true)
    expect(wrapper.find('.modal').text()).toContain('This is a test entry with some content')
    expect(wrapper.find('.modal').text()).toContain('Morning question')
    expect(wrapper.find('.modal').text()).toContain('Ведёт к целям')
  })

  it('closes detail modal when close button is clicked', async () => {
    mockListJournal.mockResolvedValueOnce(makeListResponse([ENTRY]))
    const wrapper = mount(JournalView)
    await flushPromises()

    await wrapper.find('tbody tr.clickable-row').trigger('click')
    expect(wrapper.find('.modal').exists()).toBe(true)

    await wrapper.find('.btn-close').trigger('click')
    expect(wrapper.find('.modal').exists()).toBe(false)
  })

  it('shows pagination controls when total exceeds page size', async () => {
    mockListJournal.mockResolvedValue(makeListResponse([ENTRY], 50))
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(wrapper.find('.pagination').exists()).toBe(true)
    expect(wrapper.text()).toContain('Страница 1')
  })

  it('does not show pagination when total fits in one page', async () => {
    mockListJournal.mockResolvedValueOnce(makeListResponse([ENTRY], 1))
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(wrapper.find('.pagination').exists()).toBe(false)
  })

  it('next page button loads page 2', async () => {
    mockListJournal.mockResolvedValue(makeListResponse([ENTRY], 50))
    const wrapper = mount(JournalView)
    await flushPromises()

    mockListJournal.mockClear()
    mockListJournal.mockResolvedValue(makeListResponse([ENTRY], 50))

    const nextBtn = wrapper.findAll('.pagination button').find((b) => b.text().includes('Вперёд'))
    await nextBtn!.trigger('click')
    await flushPromises()

    expect(mockListJournal).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })

  it('apply filters calls listJournal with filter params', async () => {
    const wrapper = mount(JournalView)
    await flushPromises()
    mockListJournal.mockClear()
    mockListJournal.mockResolvedValue(makeListResponse([]))

    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2024-01-01')
    await dateInputs[1].setValue('2024-01-31')

    // Button component renders as <button> — find by text
    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('Применить'))
    await applyBtn!.trigger('click')
    await flushPromises()

    expect(mockListJournal).toHaveBeenCalledWith(
      expect.objectContaining({ date_from: '2024-01-01', date_to: '2024-01-31', page: 1 }),
    )
  })

  it('shows error message when listJournal fails', async () => {
    mockListJournal.mockRejectedValueOnce(new ApiError(500, 'Server error', 'DB unavailable'))
    const wrapper = mount(JournalView)
    await flushPromises()

    expect(wrapper.text()).toContain('DB unavailable')
  })
})
