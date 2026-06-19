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
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Field from '@/components/ui/Field.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'

type KindFilter = 'all' | 'audio' | 'image'

const assets = ref<MediaAsset[]>([])
const loading = ref(false)
const listError = ref('')
const kindFilter = ref<KindFilter>('all')

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
const uploadedName = ref('')

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
  const fileName = uploadFile.value.name
  uploading.value = true
  uploadProgress.value = 0
  uploadError.value = ''
  uploadedAsset.value = null
  try {
    const asset = await uploadMediaAsset(uploadFile.value, uploadKind.value, (p) => {
      uploadProgress.value = p
    })
    uploadedAsset.value = asset
    uploadedName.value = fileName
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
      <h2 class="section-title">Загрузить файл</h2>

      <div class="upload-form">
        <Field label="Тип файла">
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
        </Field>

        <Field label="Файл">
          <input
            id="upload-file-input"
            ref="uploadFileRef"
            type="file"
            :accept="uploadKind === 'image' ? 'image/*' : 'audio/*'"
            @change="onFileChange"
          />
        </Field>

        <Button
          variant="primary"
          :disabled="!uploadFile || uploading"
          @click="doUpload"
        >
          {{ uploading ? 'Загрузка...' : 'Загрузить' }}
        </Button>

        <div v-if="uploading" class="progress-wrap">
          <div class="progress-bar" :style="{ width: `${uploadProgress}%` }"></div>
          <span class="progress-label">{{ uploadProgress }}%</span>
        </div>

        <p v-if="uploadError" class="error-msg">{{ uploadError }}</p>

        <div v-if="uploadedAsset" class="upload-result">
          <p class="success-msg">Файл загружен</p>
          <div class="asset-info">
            <div v-if="uploadedName" class="info-row">
              <span class="info-key">Имя файла</span>
              <span class="asset-name">{{ uploadedName }}</span>
            </div>
            <div class="info-row">
              <span class="info-key">UUID</span>
              <code class="asset-id">{{ uploadedAsset.id }}</code>
              <Button variant="secondary" size="sm" @click="copyId(uploadedAsset.id)">
                Копировать
              </Button>
            </div>
            <div class="info-row">
              <span class="info-key">Тип</span>
              <span>{{ uploadedAsset.kind }}</span>
            </div>
            <div v-if="uploadedAsset.telegram_file_id" class="info-row">
              <span class="info-key">Telegram file_id</span>
              <code class="asset-id small">{{ uploadedAsset.telegram_file_id }}</code>
            </div>
            <p class="hint">file_id записан и будет использоваться при отправке через Telegram.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Asset list section -->
    <section class="section">
      <h2 class="section-title">Медиафайлы</h2>

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
      <Spinner v-if="loading" pose="meditating" label="Загрузка файлов…" />

      <EmptyState
        v-else-if="!loading && filteredAssets.length === 0 && !listError"
        pose="lounging"
        label="Файлы не найдены."
      />

      <!-- Card list (mobile) -->
      <div v-if="filteredAssets.length > 0" class="card-list">
        <Card v-for="a in filteredAssets" :key="a.id">
          <div class="card-row">
            <Badge :variant="a.kind === 'image' ? 'info' : 'warning'">
              {{ a.kind === 'image' ? 'Изображение' : 'Аудио' }}
            </Badge>
            <span class="card-date">{{ formatDate(a.created_at) }}</span>
          </div>
          <code class="asset-id small">{{ a.id }}</code>
          <div class="card-actions">
            <Button variant="secondary" size="sm" @click="copyId(a.id)">Копировать</Button>
            <Button
              variant="secondary"
              size="sm"
              :disabled="!a.storage_path"
              @click="togglePreview(a)"
            >
              {{ expandedIds.has(a.id) ? 'Скрыть' : 'Просмотр' }}
            </Button>
            <Button variant="danger" size="sm" @click="removeAsset(a)">Удалить</Button>
          </div>
          <div v-if="expandedIds.has(a.id)" class="preview-cell">
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
                >Скачать</a>
              </div>
            </template>
          </div>
        </Card>
      </div>

      <!-- Table (wide screens) — keep table.media-table for tests -->
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
                        >Скачать</a>
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
      <h2 class="section-title">Пул мотивирующих изображений</h2>
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

        <Field label="Изображение *">
          <select v-model="motivAssetId" required>
            <option value="" disabled>— выберите файл —</option>
            <option v-for="a in imageAssets" :key="a.id" :value="a.id">
              {{ a.id }} ({{ a.mime ?? a.kind }})
            </option>
          </select>
        </Field>

        <div class="checkbox-field">
          <label>
            <input v-model="motivActive" type="checkbox" />
            Активно
          </label>
        </div>

        <div class="form-actions">
          <Button type="submit" variant="primary" :disabled="!motivAssetId || motivSubmitting">
            {{ motivSubmitting ? 'Добавление...' : 'Добавить в пул' }}
          </Button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section {
  border: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.section-title {
  font-size: var(--text-md);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.01em;
  margin: 0;
}

.hint {
  color: var(--color-hint);
  font-size: var(--text-sm);
}

.error-msg {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
}

.success-msg {
  color: var(--color-success);
  background: var(--color-success-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
}

/* Upload form */
.upload-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.kind-radios {
  display: flex;
  gap: var(--space-4);
  min-height: var(--tap-target);
  align-items: center;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: var(--text-base);
}

.progress-wrap {
  position: relative;
  height: 1.5rem;
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--color-accent);
  transition: width 0.15s ease;
}

.progress-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}

.upload-result {
  border: 1px solid color-mix(in srgb, var(--color-success) 40%, transparent);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-success-bg);
}

.asset-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.info-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.info-key {
  font-size: var(--text-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-hint);
  min-width: 5rem;
}

.asset-id {
  font-family: monospace;
  font-size: var(--text-sm);
  background: var(--color-surface);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  word-break: break-all;
}

.asset-id.small { font-size: var(--text-xs); }

.asset-name {
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  word-break: break-all;
}

/* Filter tabs */
.filter-tabs {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.tab-btn {
  border: 1px solid color-mix(in srgb, var(--color-hint) 40%, transparent);
  border-radius: var(--radius-md);
  padding: 0 var(--space-3);
  min-height: var(--tap-target);
  cursor: pointer;
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  background: var(--color-bg);
  color: var(--color-text);
  transition: background var(--transition-fast), color var(--transition-fast);
  font-family: var(--font-family);
}

.tab-btn.active {
  background: var(--color-accent);
  color: var(--color-accent-text);
  border-color: var(--color-accent);
}

/* Cards */
.card-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.card-date {
  font-size: var(--text-xs);
  color: var(--color-hint);
  font-variant-numeric: tabular-nums;
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-2);
  border-top: 1px solid color-mix(in srgb, var(--color-hint) 15%, transparent);
}

/* Table */
.media-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.media-table th,
.media-table td {
  text-align: left;
  padding: var(--space-2) var(--space-2);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  vertical-align: middle;
}

.media-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  white-space: nowrap;
  font-size: var(--text-xs);
}

.kind-badge {
  display: inline-block;
  border-radius: var(--radius-sm);
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.kind-image { background: var(--color-info-bg); color: var(--color-link); }
.kind-audio { background: var(--color-warning-bg); color: var(--color-warning); }

.mime-cell { color: var(--color-hint); font-size: var(--text-xs); }

.uuid-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.date-cell {
  white-space: nowrap;
  color: var(--color-hint);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}

.action-cell {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.preview-row td {
  background: var(--color-surface);
  padding: var(--space-3) var(--space-4);
}

.preview-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.preview-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: var(--radius-md);
  object-fit: contain;
}

.preview-audio { width: 100%; }

.preview-download {
  display: flex;
  justify-content: flex-end;
}

/* Motiv form */
.motiv-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.checkbox-field label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  color: var(--color-text);
  font-size: var(--text-base);
  min-height: var(--tap-target);
}

.checkbox-field input[type='checkbox'] { width: auto; }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

/* Buttons (for table/download link styling) */
.btn {
  border: none;
  border-radius: var(--radius-md);
  padding: 0 var(--space-3);
  min-height: var(--tap-target);
  cursor: pointer;
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  transition: opacity var(--transition-fast);
  font-family: var(--font-family);
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { min-height: var(--tap-target); padding: 0 var(--space-2); font-size: var(--text-xs); }
.btn-primary { background: var(--color-accent); color: var(--color-accent-text); }
.btn-secondary { background: var(--color-surface); color: var(--color-text); }
.btn-danger { background: var(--color-danger); color: #fff; }
</style>
