import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ApiError } from '@/api/client'
import MediaView from '@/views/MediaView.vue'
import type { MediaAsset } from '@/api/media'

const {
  mockListMediaAssets,
  mockUploadMediaAsset,
  mockDeleteMediaAsset,
  mockCreateMotivationalImage,
} = vi.hoisted(() => ({
  mockListMediaAssets: vi.fn(),
  mockUploadMediaAsset: vi.fn(),
  mockDeleteMediaAsset: vi.fn(),
  mockCreateMotivationalImage: vi.fn(),
}))

vi.mock('@/api/media', () => ({
  listMediaAssets: mockListMediaAssets,
  uploadMediaAsset: mockUploadMediaAsset,
  deleteMediaAsset: mockDeleteMediaAsset,
  createMotivationalImage: mockCreateMotivationalImage,
}))

const IMAGE_ASSET: MediaAsset = {
  id: 'img-1',
  kind: 'image',
  storage_path: '/uploads/img.jpg',
  telegram_file_id: null,
  mime: 'image/jpeg',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

const AUDIO_ASSET: MediaAsset = {
  id: 'aud-1',
  kind: 'audio',
  storage_path: '/uploads/audio.mp3',
  telegram_file_id: null,
  mime: 'audio/mpeg',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

describe('MediaView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockListMediaAssets.mockResolvedValue([])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('calls listMediaAssets on mount and renders assets in the table', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET, AUDIO_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    expect(mockListMediaAssets).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain(IMAGE_ASSET.id)
    expect(wrapper.text()).toContain(AUDIO_ASSET.id)
  })

  it('kind filter tabs update the visible assets in the table', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET, AUDIO_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const tableText = () => wrapper.find('table.media-table tbody').text()

    const tabs = wrapper.findAll('button.tab-btn')
    const imageTab = tabs.find((t) => t.text().includes('Изображения'))
    await imageTab!.trigger('click')

    expect(tableText()).toContain(IMAGE_ASSET.id)
    expect(tableText()).not.toContain(AUDIO_ASSET.id)

    const audioTab = tabs.find((t) => t.text().includes('Аудио'))
    await audioTab!.trigger('click')

    expect(tableText()).not.toContain(IMAGE_ASSET.id)
    expect(tableText()).toContain(AUDIO_ASSET.id)
  })

  it('upload button is disabled when no file is selected', async () => {
    const wrapper = mount(MediaView)
    await flushPromises()

    const uploadBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Загрузить'))
    expect(uploadBtn?.element.disabled).toBe(true)
  })

  it('on successful upload the new asset appears in the list', async () => {
    const newAsset: MediaAsset = { ...IMAGE_ASSET, id: 'new-img' }
    mockUploadMediaAsset.mockResolvedValueOnce(newAsset)

    const wrapper = mount(MediaView)
    await flushPromises()

    const fileInput = wrapper.find('input[type="file"]')
    const file = new File(['content'], 'new.jpg', { type: 'image/jpeg' })
    Object.defineProperty(fileInput.element, 'files', {
      value: { 0: file, item: () => file, length: 1 },
      configurable: true,
    })
    await fileInput.trigger('change')

    const uploadBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Загрузить'))
    await uploadBtn!.trigger('click')
    await flushPromises()

    expect(mockUploadMediaAsset).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('new-img')
  })

  it('image assets populate the motivational image select', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
    expect(select.text()).toContain(IMAGE_ASSET.id)
  })

  it('submitting the motiv form calls createMotivationalImage and shows success', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])
    mockCreateMotivationalImage.mockResolvedValueOnce({
      id: 'motiv-1',
      media_asset_id: IMAGE_ASSET.id,
      active: true,
    })

    const wrapper = mount(MediaView)
    await flushPromises()

    const select = wrapper.find('select')
    await select.setValue(IMAGE_ASSET.id)

    await wrapper.find('form.motiv-form').trigger('submit')
    await flushPromises()

    expect(mockCreateMotivationalImage).toHaveBeenCalledWith({
      media_asset_id: IMAGE_ASSET.id,
      active: true,
    })
    expect(wrapper.text()).toContain('Изображение добавлено в пул мотивации')
  })

  it('shows error banner when createMotivationalImage fails', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])
    mockCreateMotivationalImage.mockRejectedValueOnce(
      new ApiError(500, 'Server error', 'Storage unavailable'),
    )

    const wrapper = mount(MediaView)
    await flushPromises()

    const select = wrapper.find('select')
    await select.setValue(IMAGE_ASSET.id)

    await wrapper.find('form.motiv-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Storage unavailable')
  })
})
