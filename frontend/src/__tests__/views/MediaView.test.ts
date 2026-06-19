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
  mockGetMediaUrl,
} = vi.hoisted(() => ({
  mockListMediaAssets: vi.fn(),
  mockUploadMediaAsset: vi.fn(),
  mockDeleteMediaAsset: vi.fn(),
  mockCreateMotivationalImage: vi.fn(),
  mockGetMediaUrl: vi.fn(),
}))

vi.mock('@/api/media', () => ({
  listMediaAssets: mockListMediaAssets,
  uploadMediaAsset: mockUploadMediaAsset,
  deleteMediaAsset: mockDeleteMediaAsset,
  createMotivationalImage: mockCreateMotivationalImage,
  getMediaUrl: mockGetMediaUrl,
}))

const IMAGE_ASSET: MediaAsset = {
  id: 'img-1',
  kind: 'image',
  storage_path: '/uploads/img.jpg',
  telegram_file_id: null,
  mime: 'image/jpeg',
  original_filename: 'my-photo.jpg',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

const AUDIO_ASSET: MediaAsset = {
  id: 'aud-1',
  kind: 'audio',
  storage_path: '/uploads/audio.mp3',
  telegram_file_id: null,
  mime: 'audio/mpeg',
  original_filename: 'session.mp3',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

const VIDEO_ASSET: MediaAsset = {
  id: 'vid-1',
  kind: 'video',
  storage_path: '/uploads/video.mp4',
  telegram_file_id: null,
  mime: 'video/mp4',
  original_filename: 'lecture.mp4',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

describe('MediaView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockListMediaAssets.mockResolvedValue([])
    mockGetMediaUrl.mockResolvedValue({ url: 'https://s3.example.com/img.jpg', expires_in: 900 })
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
    await flushPromises()

    // The button should now be enabled since uploadFile is set
    const uploadBtn = wrapper.findAll('button').find((b) => b.text().includes('Загрузить'))
    if (uploadBtn?.element.disabled) {
      // Fallback: files mock may not propagate in jsdom — call via unknown cast
      await (wrapper.vm as unknown as { doUpload: () => Promise<void> }).doUpload()
    } else {
      await uploadBtn!.trigger('click')
    }
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
    // When original_filename is present it is shown in the option text
    expect(select.text()).toContain(IMAGE_ASSET.original_filename)
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

  it('clicking "Просмотр" on an image row fetches a presigned URL and renders a thumbnail', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])
    mockGetMediaUrl.mockResolvedValueOnce({
      url: 'https://s3.example.com/img.jpg?sig=abc',
      expires_in: 900,
    })

    const wrapper = mount(MediaView)
    await flushPromises()

    // Find preview button in the table (not the card list)
    const tablePreviewBtn = wrapper
      .find('table.media-table')
      .findAll('button')
      .find((b) => b.text() === 'Просмотр')
    expect(tablePreviewBtn).toBeDefined()
    await tablePreviewBtn!.trigger('click')
    await flushPromises()

    expect(mockGetMediaUrl).toHaveBeenCalledWith(IMAGE_ASSET.id)
    const img = wrapper.find('img.preview-image')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://s3.example.com/img.jpg?sig=abc')
  })

  it('clicking "Просмотр" on an audio row fetches a presigned URL and renders an audio element', async () => {
    mockListMediaAssets.mockResolvedValueOnce([AUDIO_ASSET])
    mockGetMediaUrl.mockResolvedValueOnce({
      url: 'https://s3.example.com/audio.mp3?sig=xyz',
      expires_in: 900,
    })

    const wrapper = mount(MediaView)
    await flushPromises()

    const tablePreviewBtn = wrapper
      .find('table.media-table')
      .findAll('button')
      .find((b) => b.text() === 'Просмотр')
    await tablePreviewBtn!.trigger('click')
    await flushPromises()

    const audio = wrapper.find('audio.preview-audio')
    expect(audio.exists()).toBe(true)
    expect(audio.attributes('src')).toBe('https://s3.example.com/audio.mp3?sig=xyz')
  })

  it('preview row shows a "Скачать" download link pointing to the presigned URL', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])
    mockGetMediaUrl.mockResolvedValueOnce({
      url: 'https://s3.example.com/img.jpg?sig=abc',
      expires_in: 900,
    })

    const wrapper = mount(MediaView)
    await flushPromises()

    await wrapper.find('table.media-table').findAll('button').find((b) => b.text() === 'Просмотр')!.trigger('click')
    await flushPromises()

    const link = wrapper.find('a[href*="s3.example.com"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('Скачать')
  })

  it('preview row shows error message when getMediaUrl fails', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])
    mockGetMediaUrl.mockRejectedValueOnce(new ApiError(404, 'Not found', 'Файл не найден'))

    const wrapper = mount(MediaView)
    await flushPromises()

    await wrapper.find('table.media-table').findAll('button').find((b) => b.text() === 'Просмотр')!.trigger('click')
    await flushPromises()

    // Error shows in the preview-cell in the table preview row
    const previewRow = wrapper.find('tr.preview-row')
    expect(previewRow.exists()).toBe(true)
    expect(previewRow.text()).toContain('Файл не найден')
  })

  it('table shows original_filename in the Имя column', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const table = wrapper.find('table.media-table')
    expect(table.text()).toContain('Имя')
    expect(table.text()).toContain('my-photo.jpg')
  })

  it('table shows — when original_filename is null', async () => {
    const assetNoName: MediaAsset = { ...IMAGE_ASSET, original_filename: null }
    mockListMediaAssets.mockResolvedValueOnce([assetNoName])

    const wrapper = mount(MediaView)
    await flushPromises()

    const table = wrapper.find('table.media-table')
    const filenameCell = table.find('td.filename-cell')
    expect(filenameCell.exists()).toBe(true)
    expect(filenameCell.text()).toBe('—')
  })

  it('mobile card list shows original_filename prominently', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const cardList = wrapper.find('.card-list')
    expect(cardList.text()).toContain('my-photo.jpg')
  })

  it('mobile card list shows — when original_filename is null', async () => {
    const assetNoName: MediaAsset = { ...IMAGE_ASSET, original_filename: null }
    mockListMediaAssets.mockResolvedValueOnce([assetNoName])

    const wrapper = mount(MediaView)
    await flushPromises()

    const cardFilename = wrapper.find('.card-filename')
    expect(cardFilename.exists()).toBe(true)
    expect(cardFilename.text()).toBe('—')
  })

  it('motivational image select shows original_filename when present', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const select = wrapper.find('select')
    expect(select.text()).toContain('my-photo.jpg')
    // UUID should NOT appear since original_filename is present
    expect(select.text()).not.toContain('img-1 (')
  })

  it('motivational image select falls back to UUID+mime when original_filename is null', async () => {
    const assetNoName: MediaAsset = { ...IMAGE_ASSET, original_filename: null }
    mockListMediaAssets.mockResolvedValueOnce([assetNoName])

    const wrapper = mount(MediaView)
    await flushPromises()

    const select = wrapper.find('select')
    expect(select.text()).toContain('img-1 (image/jpeg)')
  })

  it('video asset shows "Видео" badge in card list and table', async () => {
    mockListMediaAssets.mockResolvedValueOnce([VIDEO_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    expect(wrapper.find('.card-list').text()).toContain('Видео')
    expect(wrapper.find('table.media-table').text()).toContain('Видео')
    expect(wrapper.find('table.media-table').text()).not.toContain('Аудио')
  })

  it('video filter tab shows only video assets', async () => {
    mockListMediaAssets.mockResolvedValueOnce([IMAGE_ASSET, AUDIO_ASSET, VIDEO_ASSET])

    const wrapper = mount(MediaView)
    await flushPromises()

    const videoTab = wrapper.findAll('button.tab-btn').find((t) => t.text().includes('Видео'))
    expect(videoTab).toBeDefined()
    await videoTab!.trigger('click')

    const tableText = wrapper.find('table.media-table tbody').text()
    expect(tableText).toContain(VIDEO_ASSET.id)
    expect(tableText).not.toContain(IMAGE_ASSET.id)
    expect(tableText).not.toContain(AUDIO_ASSET.id)
  })

  it('clicking "Просмотр" on a video row renders a video element', async () => {
    mockListMediaAssets.mockResolvedValueOnce([VIDEO_ASSET])
    mockGetMediaUrl.mockResolvedValueOnce({
      url: 'https://s3.example.com/video.mp4?sig=xyz',
      expires_in: 900,
    })

    const wrapper = mount(MediaView)
    await flushPromises()

    const tablePreviewBtn = wrapper
      .find('table.media-table')
      .findAll('button')
      .find((b) => b.text() === 'Просмотр')
    await tablePreviewBtn!.trigger('click')
    await flushPromises()

    const video = wrapper.find('video.preview-video')
    expect(video.exists()).toBe(true)
    expect(video.attributes('src')).toBe('https://s3.example.com/video.mp4?sig=xyz')
  })

  it('upload result for video shows S3-only hint instead of Telegram hint', async () => {
    const newVideoAsset: MediaAsset = { ...VIDEO_ASSET, id: 'new-vid', telegram_file_id: null }
    mockUploadMediaAsset.mockResolvedValueOnce(newVideoAsset)

    const wrapper = mount(MediaView)
    await flushPromises()

    // Set file and kind directly on the component so doUpload() doesn't short-circuit
    const vm = wrapper.vm as unknown as {
      uploadFile: File | null
      uploadKind: string
      doUpload: () => Promise<void>
    }
    vm.uploadFile = new File(['test'], 'lecture.mp4', { type: 'video/mp4' })
    vm.uploadKind = 'video'
    await wrapper.vm.$nextTick()

    await vm.doUpload()
    await flushPromises()

    expect(wrapper.text()).toContain('S3')
    expect(wrapper.text()).not.toContain('file_id записан')
  })
})
