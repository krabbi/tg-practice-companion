import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PracticesView from '@/views/PracticesView.vue'
import type { MediaAsset } from '@/api/media'

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

const mockUploadMediaAsset = vi.fn<
  [File, 'audio' | 'image' | 'video', ((p: number) => void)?],
  Promise<MediaAsset>
>()

vi.mock('@/api/media', () => ({
  uploadMediaAsset: (...args: Parameters<typeof mockUploadMediaAsset>) =>
    mockUploadMediaAsset(...args),
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
    // Button component renders as button.ui-btn--primary
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Добавить'))
    await addBtn!.trigger('click')
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

describe('PracticesView video upload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('auth_token', 'test-token')
    stubFetch([])
    mockUploadMediaAsset.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    localStorage.clear()
  })

  async function openFormWithVideoType() {
    const wrapper = mount(PracticesView, { global: { plugins: [] } })
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Добавить'))
    await addBtn!.trigger('click')

    const selects = wrapper.findAll('select')
    const contentTypeSelect = selects.find((s) =>
      s.findAll('option').some((o) => o.element.value === 'video'),
    )
    await contentTypeSelect!.setValue('video')
    await flushPromises()

    return wrapper
  }

  it('has Video option in content-type selector', async () => {
    const wrapper = mount(PracticesView, { global: { plugins: [] } })
    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Добавить'))
    await addBtn!.trigger('click')

    const selects = wrapper.findAll('select')
    const contentTypeSelect = selects.find((s) =>
      s.findAll('option').some((o) => o.element.value === 'video'),
    )
    expect(contentTypeSelect).toBeDefined()
    const videoOption = contentTypeSelect!
      .findAll('option')
      .find((o) => o.element.value === 'video')
    expect(videoOption).toBeDefined()
    expect(videoOption!.text()).toBe('Видео')
  })

  it('shows file picker with accept="video/*" when video is selected', async () => {
    const wrapper = await openFormWithVideoType()

    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)
    expect(fileInput.attributes('accept')).toBe('video/*')
  })

  it('does not show UUID text input when video is selected', async () => {
    const wrapper = await openFormWithVideoType()

    const uuidInput = wrapper.find('input[placeholder="UUID из раздела Медиа"]')
    expect(uuidInput.exists()).toBe(false)
  })

  it('shows upload button after file is selected', async () => {
    const wrapper = await openFormWithVideoType()

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['video-data'], 'test.mp4', { type: 'video/mp4' })
    Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
    await fileInput.trigger('change')
    await flushPromises()

    const uploadBtn = wrapper.findAll('button').find((b) => b.text() === 'Загрузить')
    expect(uploadBtn).toBeDefined()
    expect(uploadBtn!.exists()).toBe(true)
  })

  it('shows progress bar during upload', async () => {
    let progressCallback: ((p: number) => void) | undefined
    mockUploadMediaAsset.mockImplementation(
      (_file, _kind, onProgress) =>
        new Promise((resolve) => {
          progressCallback = onProgress
          setTimeout(() => resolve({ id: 'asset-uuid' } as MediaAsset), 100)
        }),
    )

    const wrapper = await openFormWithVideoType()

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['video-data'], 'test.mp4', { type: 'video/mp4' })
    Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
    await fileInput.trigger('change')
    await flushPromises()

    const uploadBtn = wrapper.findAll('button').find((b) => b.text() === 'Загрузить')
    await uploadBtn!.trigger('click')

    progressCallback?.(42)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.progress-wrap').exists()).toBe(true)
    expect(wrapper.find('.progress-label').text()).toBe('42%')
  })

  it('displays inline error when upload fails', async () => {
    const { ApiError } = await import('@/api/client')
    mockUploadMediaAsset.mockRejectedValue(new ApiError(413, 'Too Large', 'Файл слишком большой'))

    const wrapper = await openFormWithVideoType()

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['video-data'], 'huge.mp4', { type: 'video/mp4' })
    Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
    await fileInput.trigger('change')
    await flushPromises()

    const uploadBtn = wrapper.findAll('button').find((b) => b.text() === 'Загрузить')
    await uploadBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.upload-error').exists()).toBe(true)
    expect(wrapper.find('.upload-error').text()).toBe('Файл слишком большой')
  })

  it('sets media_asset_id and shows success message after successful upload', async () => {
    const asset: MediaAsset = {
      id: 'returned-uuid',
      kind: 'video',
      storage_path: 'video/returned-uuid.mp4',
      telegram_file_id: null,
      mime: 'video/mp4',
      original_filename: 'test.mp4',
      created_at: '2026-06-19T00:00:00Z',
      updated_at: '2026-06-19T00:00:00Z',
    }
    mockUploadMediaAsset.mockResolvedValue(asset)

    const wrapper = await openFormWithVideoType()

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['video-data'], 'test.mp4', { type: 'video/mp4' })
    Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
    await fileInput.trigger('change')
    await flushPromises()

    const uploadBtn = wrapper.findAll('button').find((b) => b.text() === 'Загрузить')
    await uploadBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.upload-success').exists()).toBe(true)
    expect(wrapper.find('.upload-success').text()).toContain('returned-uuid')
  })

  it('passes video/* file with kind=video to uploadMediaAsset', async () => {
    const asset: MediaAsset = {
      id: 'asset-id',
      kind: 'video',
      storage_path: null,
      telegram_file_id: null,
      mime: 'video/mp4',
      original_filename: 'clip.mp4',
      created_at: '2026-06-19T00:00:00Z',
      updated_at: '2026-06-19T00:00:00Z',
    }
    mockUploadMediaAsset.mockResolvedValue(asset)

    const wrapper = await openFormWithVideoType()

    const file = new File(['data'], 'clip.mp4', { type: 'video/mp4' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
    await fileInput.trigger('change')
    await flushPromises()

    const uploadBtn = wrapper.findAll('button').find((b) => b.text() === 'Загрузить')
    await uploadBtn!.trigger('click')
    await flushPromises()

    expect(mockUploadMediaAsset).toHaveBeenCalledWith(file, 'video', expect.any(Function))
  })
})
