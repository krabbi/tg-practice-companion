<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import {
  uploadMediaAsset,
  listMediaAssets,
  deleteMediaAsset,
  createMotivationalImage,
  getMediaUrl,
  type MediaAsset,
} from '@/api/media'

type KindFilter = 'all' | 'audio' | 'image'

const assets = ref<MediaAsset[]>([])
const loading = ref(false)
const listError = ref('')
const kindFilter = ref<KindFilter>('all')

// Per-asset preview state: id → { url, loading, error }
const previewUrls = ref<Record<string, string>>({})
const previewLoading = ref<Record<string, boolean>>({})
const previewErrors = ref<Record<string, string>>({})
const expandedIds = ref<Set<string>>(new Set())

const uploadFileRef = ref<HTMLInputElement | null>(null)
const uploadFile = ref<File | null>(null)
const uploadKind = ref<'audio' | 'image'>('image')
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const uploadedAsset = ref<MediaAsset | null>(null)

const motivAssetId = ref('')
const motivActive = ref(true)
const motivSubmitting = ref(false)
const motivError = ref('')
const motivSuccess = ref('')

const filteredAssets = computed<MediaAsset[]>(() => {
  if (kindFilter.value === 'all') return assets.value
  return assets.value.filter((a) => a.kind === kindFilter.value)
})

const imageAssets = computed<MediaAsset[]>(() => assets.value.filter((a) => a.kind === 'image'))

async function loadAssets(): Promise<void> {
  loading.value = true
  listError.value = ''
  try {
    assets.value = await listMediaAssets()
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function onFileChange(e: Event): void {
  const target = e.target as HTMLInputElement
  uploadFile.value = target.files?.[0] ?? null
  uploadedAsset.value = null
  uploadError.value = ''
}

async function doUpload(): Promise<void> {
  if (!uploadFile.value) return
  uploading.value = true
  uploadProgress.value = 0
  uploadError.value = ''
  uploadedAsset.value = null
  try {
    const asset = await uploadMediaAsset(uploadFile.value, uploadKind.value, (p) => {
      uploadProgress.value = p
    })
    uploadedAsset.value = asset
    assets.value.unshift(asset)
    uploadFile.value = null
    if (uploadFileRef.value) uploadFileRef.value.value = ''
  } catch (e) {
    uploadError.value =
      e instanceof ApiError
        ? (e.detail ?? `Ошибка ${e.status}`)
        : 'Ошибка загрузки'
  } finally {
    uploading.value = false
  }
}

async function removeAsset(asset: MediaAsset): Promise<void> {
  const label = asset.mime ?? asset.kind
  if (!confirm(`Удалить медиафайл (${label})?`)) return
  try {
    await deleteMediaAsset(asset.id)
    assets.value = assets.value.filter((a) => a.id !== asset.id)
    if (uploadedAsset.value?.id === asset.id) uploadedAsset.value = null
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка удаления'
  }
}

async function addToPool(): Promise<void> {
  if (!motivAssetId.value) return
  motivSubmitting.value = true
  motivError.value = ''
  motivSuccess.value = ''
  try {
    await createMotivationalImage({ media_asset_id: motivAssetId.value, active: motivActive.value })
    motivSuccess.value = 'Изображение добавлено в пул мотивации'
    motivAssetId.value = ''
    motivActive.value = true
  } catch (e) {
    motivError.value =
      e instanceof ApiError ? (e.detail ?? `Ошибка ${e.status}`) : 'Неизвестная ошибка'
  } finally {
    motivSubmitting.value = false
  }
}

async function togglePreview(asset: MediaAsset): Promise<void> {
  const id = asset.id
  if (expandedIds.value.has(id)) {
    expandedIds.value = new Set([...expandedIds.value].filter((x) => x !== id))
    return
  }
  expandedIds.value = new Set([...expandedIds.value, id])
  if (previewUrls.value[id] || previewLoading.value[id]) return
  previewLoading.value = { ...previewLoading.value, [id]: true }
  previewErrors.value = { ...previewErrors.value, [id]: '' }
  try {
    const { url } = await getMediaUrl(id)
    previewUrls.value = { ...previewUrls.value, [id]: url }
  } catch (e) {
    previewErrors.value = {
      ...previewErrors.value,
      [id]: e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки ссылки',
    }
  } finally {
    previewLoading.value = { ...previewLoading.value, [id]: false }
  }
}

function copyId(id: string): void {
  void navigator.clipboard.writeText(id)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

onMounted(loadAssets)
</script>

<template>
  <div class="view">
    <!-- Upload section -->
    <section class="section">
      <h2>Загрузить файл</h2>

      <div class="upload-form">
        <div class="field">
          <label>Тип файла</label>
          <div class="kind-radios">
            <label class="radio-label">
              <input v-model="uploadKind" type="radio" value="image" />
              Изображение
            </label>
            <label class="radio-label">
              <input v-model="uploadKind" type="radio" value="audio" />
              Аудио
            </label>
          </div>
        </div>

        <div class="field">
          <label>Файл</label>
          <input
            id="upload-file-input"
            ref="uploadFileRef"
            type="file"
            :accept="uploadKind === 'image' ? 'image/*' : 'audio/*'"
            @change="onFileChange"
          />
        </div>

        <button
          class="btn btn-primary"
          :disabled="!uploadFile || uploading"
          @click="doUpload"
        >
          {{ uploading ? 'Загрузка...' : 'Загрузить' }}
        </button>

        <div v-if="uploading" class="progress-wrap">
          <div class="progress-bar" :style="{ width: `${uploadProgress}%` }"></div>
          <span class="progress-label">{{ uploadProgress }}%</span>
        </div>

        <p v-if="uploadError" class="error-msg">{{ uploadError }}</p>

        <div v-if="uploadedAsset" class="upload-result">
          <p class="success-msg">Файл загружен</p>
          <div class="asset-info">
            <div class="info-row">
              <span class="info-key">UUID</span>
              <code class="asset-id">{{ uploadedAsset.id }}</code>
              <button class="btn btn-sm btn-secondary" @click="copyId(uploadedAsset.id)">
                Копировать
              </button>
            </div>
            <div class="info-row">
              <span class="info-key">Тип</span>
              <span>{{ uploadedAsset.kind }}</span>
            </div>
            <div v-if="uploadedAsset.telegram_file_id" class="info-row">
              <span class="info-key">Telegram file_id</span>
              <code class="asset-id small">{{ uploadedAsset.telegram_file_id }}</code>
            </div>
            <p class="hint">
              file_id записан и будет использоваться при отправке через Telegram.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Asset list section -->
    <section class="section">
      <h2>Медиафайлы</h2>

      <div class="filter-tabs">
        <button
          class="tab-btn"
          :class="{ active: kindFilter === 'all' }"
          @click="kindFilter = 'all'"
        >
          Все ({{ assets.length }})
        </button>
        <button
          class="tab-btn"
          :class="{ active: kindFilter === 'image' }"
          @click="kindFilter = 'image'"
        >
          Изображения
        </button>
        <button
          class="tab-btn"
          :class="{ active: kindFilter === 'audio' }"
          @click="kindFilter = 'audio'"
        >
          Аудио
        </button>
      </div>

      <p v-if="listError" class="error-msg">{{ listError }}</p>
      <p v-if="loading" class="hint">Загрузка...</p>

      <div v-if="!loading && filteredAssets.length === 0 && !listError" class="hint">
        Файлы не найдены.
      </div>

      <div v-if="filteredAssets.length > 0" class="table-wrap">
        <table class="media-table">
          <thead>
            <tr>
              <th>Тип</th>
              <th>MIME</th>
              <th>UUID</th>
              <th>Дата</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="a in filteredAssets" :key="a.id">
              <tr>
                <td>
                  <span class="kind-badge" :class="`kind-${a.kind}`">
                    {{ a.kind === 'image' ? '🖼 Изобр.' : '🔊 Аудио' }}
                  </span>
                </td>
                <td class="mime-cell">{{ a.mime ?? '—' }}</td>
                <td>
                  <div class="uuid-cell">
                    <code class="asset-id small">{{ a.id }}</code>
                    <button class="btn btn-sm btn-secondary" @click="copyId(a.id)">
                      Копировать
                    </button>
                  </div>
                </td>
                <td class="date-cell">{{ formatDate(a.created_at) }}</td>
                <td>
                  <div class="action-cell">
                    <button
                      class="btn btn-sm btn-secondary"
                      :disabled="!a.storage_path"
                      @click="togglePreview(a)"
                    >
                      {{ expandedIds.has(a.id) ? 'Скрыть' : 'Просмотр' }}
                    </button>
                    <button class="btn btn-sm btn-danger" @click="removeAsset(a)">Удалить</button>
                  </div>
                </td>
              </tr>
              <tr v-if="expandedIds.has(a.id)" class="preview-row">
                <td colspan="5">
                  <div class="preview-cell">
                    <p v-if="previewLoading[a.id]" class="hint">Загрузка...</p>
                    <p v-else-if="previewErrors[a.id]" class="error-msg">{{ previewErrors[a.id] }}</p>
                    <template v-else-if="previewUrls[a.id]">
                      <img
                        v-if="a.kind === 'image'"
                        :src="previewUrls[a.id]"
                        class="preview-image"
                        alt="Предпросмотр"
                      />
                      <audio
                        v-else-if="a.kind === 'audio'"
                        :src="previewUrls[a.id]"
                        controls
                        class="preview-audio"
                      />
                      <div class="preview-download">
                        <a
                          :href="previewUrls[a.id]"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="btn btn-sm btn-secondary"
                        >
                          Скачать
                        </a>
                      </div>
                    </template>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Motivational images pool section -->
    <section class="section">
      <h2>Пул мотивирующих изображений</h2>
      <p class="hint">
        Добавьте изображение из загруженных медиафайлов в пул. Бот будет отправлять их
        в рамках практики «motivational_image».
      </p>

      <div v-if="imageAssets.length === 0" class="hint">
        Нет загруженных изображений. Сначала загрузите файл с типом «Изображение».
      </div>

      <form v-else class="motiv-form" @submit.prevent="addToPool">
        <p v-if="motivError" class="error-msg">{{ motivError }}</p>
        <p v-if="motivSuccess" class="success-msg">{{ motivSuccess }}</p>

        <div class="field">
          <label>Изображение *</label>
          <select v-model="motivAssetId" required>
            <option value="" disabled>— выберите файл —</option>
            <option v-for="a in imageAssets" :key="a.id" :value="a.id">
              {{ a.id }} ({{ a.mime ?? a.kind }})
            </option>
          </select>
        </div>

        <div class="field checkbox-field">
          <label>
            <input v-model="motivActive" type="checkbox" />
            Активно
          </label>
        </div>

        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="!motivAssetId || motivSubmitting">
            {{ motivSubmitting ? 'Добавление...' : 'Добавить в пул' }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.section {
  border: 1px solid var(--tg-theme-hint-color, #ddd);
  border-radius: 10px;
  padding: 1.25rem;
}

.section h2 {
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
}

.hint {
  color: var(--tg-theme-hint-color, #888);
  font-size: 0.875rem;
  margin: 0.5rem 0;
}

.error-msg {
  color: #c0392b;
  background: #fdecea;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

.success-msg {
  color: #1a7a3e;
  background: #e9f7ef;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

/* Upload form */
.upload-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.kind-radios {
  display: flex;
  gap: 1.5rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.progress-wrap {
  position: relative;
  height: 1.5rem;
  background: var(--tg-theme-secondary-bg-color, #eee);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--tg-theme-button-color, #2481cc);
  transition: width 0.15s ease;
}

.progress-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000);
}

.upload-result {
  border: 1px solid #a8d8a8;
  border-radius: 6px;
  padding: 0.75rem;
  background: #f0faf0;
}

.upload-result .success-msg {
  margin: 0 0 0.5rem 0;
}

.asset-info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.info-key {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--tg-theme-hint-color, #666);
  min-width: 5rem;
}

.asset-id {
  font-family: monospace;
  font-size: 0.8rem;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  word-break: break-all;
}

.asset-id.small {
  font-size: 0.72rem;
}

/* Filter tabs */
.filter-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.tab-btn {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.3rem 0.75rem;
  cursor: pointer;
  font-size: 0.8rem;
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #333);
  transition: background 0.15s, color 0.15s;
}

.tab-btn.active {
  background: var(--tg-theme-button-color, #2481cc);
  color: var(--tg-theme-button-text-color, #fff);
  border-color: var(--tg-theme-button-color, #2481cc);
}

/* Media table */
.table-wrap {
  overflow-x: auto;
}

.media-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.media-table th,
.media-table td {
  text-align: left;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
  vertical-align: middle;
}

.media-table th {
  font-weight: 600;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
  white-space: nowrap;
}

.kind-badge {
  display: inline-block;
  border-radius: 4px;
  padding: 0.15rem 0.4rem;
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
}

.kind-image {
  background: #e8f4fd;
  color: #1a5276;
}

.kind-audio {
  background: #fef9e7;
  color: #7d6608;
}

.mime-cell {
  color: var(--tg-theme-hint-color, #777);
  font-size: 0.8rem;
}

.uuid-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.date-cell {
  white-space: nowrap;
  color: var(--tg-theme-hint-color, #777);
  font-size: 0.8rem;
}

.action-cell {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.preview-row td {
  background: var(--tg-theme-secondary-bg-color, #f9f9f9);
  padding: 0.75rem 1rem;
}

.preview-cell {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preview-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 6px;
  object-fit: contain;
}

.preview-audio {
  width: 100%;
}

.preview-download {
  display: flex;
  justify-content: flex-end;
}

/* Motivational form */
.motiv-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* Shared field styles */
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--tg-theme-hint-color, #666);
}

.field input[type='file'],
.field select {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
  font-size: 0.875rem;
  background: var(--tg-theme-secondary-bg-color, #fafafa);
  color: var(--tg-theme-text-color, #000);
  width: 100%;
  box-sizing: border-box;
}

.checkbox-field label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: var(--tg-theme-text-color, #000);
  font-size: 0.875rem;
  font-weight: 400;
}

.checkbox-field input[type='checkbox'] {
  width: auto;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.25rem;
}

/* Buttons */
.btn {
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
}

.btn-primary {
  background: var(--tg-theme-button-color, #2481cc);
  color: var(--tg-theme-button-text-color, #fff);
}

.btn-secondary {
  background: var(--tg-theme-secondary-bg-color, #e0e0e0);
  color: var(--tg-theme-text-color, #333);
}

.btn-danger {
  background: #e74c3c;
  color: #fff;
}
</style>
