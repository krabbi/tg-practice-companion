<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import {
  listPractices,
  createPractice,
  updatePractice,
  deletePractice,
  type Practice,
  type ContentType,
  type PeriodicityType,
} from '@/api/practices'
import { uploadMediaAsset } from '@/api/media'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Field from '@/components/ui/Field.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: 'question', label: 'Вопрос' },
  { value: 'text', label: 'Текст' },
  { value: 'audio', label: 'Аудио' },
  { value: 'image', label: 'Изображение' },
  { value: 'video', label: 'Видео' },
  { value: 'want', label: 'Хочу' },
  { value: 'good_deeds', label: 'Добрые дела' },
  { value: 'motivational_image', label: 'Мотивирующее изображение' },
]

const MEDIA_CONTENT_TYPES: ContentType[] = ['audio', 'image', 'motivational_image']
const TEXT_CONTENT_TYPES: ContentType[] = ['question', 'text', 'want', 'good_deeds']

interface FormData {
  name: string
  content_type: ContentType
  content: string
  media_asset_id: string
  periodicity_type: PeriodicityType
  interval_hours: number | null
  anchor_hour: number
  anchor_minute: number
  schedule_times: string[]
  active: boolean
  start_date: string
  end_date: string
  sort_order: number
}

const EMPTY_FORM = (): FormData => ({
  name: '',
  content_type: 'question',
  content: '',
  media_asset_id: '',
  periodicity_type: 'every_n_hours',
  interval_hours: null,
  anchor_hour: 6,
  anchor_minute: 0,
  schedule_times: [],
  active: true,
  start_date: '',
  end_date: '',
  sort_order: 0,
})

const HHMM_RE = /^([01]\d|2[0-3]):([0-5]\d)$/

const practices = ref<Practice[]>([])
const loading = ref(false)
const listError = ref('')

const showForm = ref(false)
const editingId = ref<string | null>(null)
const formData = reactive<FormData>(EMPTY_FORM())
const newTime = ref('')
const formError = ref('')
const formErrors = reactive<Record<string, string>>({})
const submitting = ref(false)

const showContentField = computed(() => TEXT_CONTENT_TYPES.includes(formData.content_type))
const showMediaField = computed(() => MEDIA_CONTENT_TYPES.includes(formData.content_type))
const showVideoField = computed(() => formData.content_type === 'video')

const videoFileRef = ref<HTMLInputElement | null>(null)
const videoFile = ref<File | null>(null)
const videoUploading = ref(false)
const videoProgress = ref(0)
const videoUploadError = ref('')

function resetVideoUpload(): void {
  videoFile.value = null
  videoUploading.value = false
  videoProgress.value = 0
  videoUploadError.value = ''
  if (videoFileRef.value) videoFileRef.value.value = ''
}

watch(
  () => formData.content_type,
  () => resetVideoUpload(),
)

function onVideoFileChange(e: Event): void {
  const target = e.target as HTMLInputElement
  videoFile.value = target.files?.[0] ?? null
  videoUploadError.value = ''
}

async function uploadVideoFile(): Promise<void> {
  if (!videoFile.value) return
  videoUploading.value = true
  videoProgress.value = 0
  videoUploadError.value = ''
  try {
    const asset = await uploadMediaAsset(videoFile.value, 'video', (p) => {
      videoProgress.value = p
    })
    formData.media_asset_id = asset.id
    videoFile.value = null
    if (videoFileRef.value) videoFileRef.value.value = ''
  } catch (e) {
    videoUploadError.value =
      e instanceof ApiError ? (e.detail ?? `Ошибка ${e.status}`) : 'Ошибка загрузки'
  } finally {
    videoUploading.value = false
  }
}

function contentTypeLabel(ct: ContentType): string {
  return CONTENT_TYPES.find((c) => c.value === ct)?.label ?? ct
}

function cadenceSummary(p: Practice): string {
  if (p.periodicity_type === 'every_n_hours') {
    const h = String(p.anchor_hour ?? 0).padStart(2, '0')
    const m = String(p.anchor_minute ?? 0).padStart(2, '0')
    return `Каждые ${p.interval_hours ?? '?'} ч (с ${h}:${m})`
  }
  return p.schedule_times?.join(', ') ?? '—'
}

async function loadPractices(): Promise<void> {
  loading.value = true
  listError.value = ''
  try {
    practices.value = await listPractices()
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingId.value = null
  Object.assign(formData, EMPTY_FORM())
  newTime.value = ''
  formError.value = ''
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  resetVideoUpload()
  showForm.value = true
}

function openEdit(p: Practice): void {
  editingId.value = p.id
  Object.assign(formData, {
    name: p.name,
    content_type: p.content_type,
    content: p.content ?? '',
    media_asset_id: p.media_asset_id ?? '',
    periodicity_type: p.periodicity_type,
    interval_hours: p.interval_hours,
    anchor_hour: p.anchor_hour ?? 6,
    anchor_minute: p.anchor_minute ?? 0,
    schedule_times: [...(p.schedule_times ?? [])],
    active: p.active,
    start_date: p.start_date ? p.start_date.slice(0, 10) : '',
    end_date: p.end_date ? p.end_date.slice(0, 10) : '',
    sort_order: p.sort_order,
  })
  newTime.value = ''
  formError.value = ''
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  resetVideoUpload()
  showForm.value = true
}

function closeForm(): void {
  showForm.value = false
  editingId.value = null
}

function addTime(): void {
  const t = newTime.value.trim()
  if (!HHMM_RE.test(t)) {
    formErrors['schedule_times'] = 'Введите время в формате ЧЧ:ММ'
    return
  }
  if (!formData.schedule_times.includes(t)) {
    formData.schedule_times.push(t)
    formData.schedule_times.sort()
  }
  newTime.value = ''
  delete formErrors['schedule_times']
}

function removeTime(t: string): void {
  formData.schedule_times = formData.schedule_times.filter((x) => x !== t)
}

function validateForm(): boolean {
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  let valid = true

  if (!formData.name.trim()) {
    formErrors['name'] = 'Название обязательно'
    valid = false
  }

  if (formData.periodicity_type === 'every_n_hours') {
    if (!formData.interval_hours || formData.interval_hours < 1) {
      formErrors['interval_hours'] = 'Укажите интервал (≥ 1)'
      valid = false
    }
  } else {
    if (formData.schedule_times.length === 0) {
      formErrors['schedule_times'] = 'Добавьте хотя бы одно время'
      valid = false
    }
  }

  if (showContentField.value && !formData.content.trim()) {
    formErrors['content'] = 'Содержимое обязательно'
    valid = false
  }

  return valid
}

async function submitForm(): Promise<void> {
  if (!validateForm()) return

  formError.value = ''
  submitting.value = true

  const payload = {
    name: formData.name.trim(),
    content_type: formData.content_type,
    content: showContentField.value ? formData.content.trim() || null : null,
    media_asset_id: showMediaField.value ? formData.media_asset_id.trim() || null : null,
    periodicity_type: formData.periodicity_type,
    interval_hours:
      formData.periodicity_type === 'every_n_hours' ? (formData.interval_hours ?? undefined) : null,
    anchor_hour: formData.anchor_hour,
    anchor_minute: formData.anchor_minute,
    schedule_times: formData.periodicity_type === 'fixed_times' ? formData.schedule_times : null,
    active: formData.active,
    start_date: formData.start_date || null,
    end_date: formData.end_date || null,
    sort_order: formData.sort_order,
  }

  try {
    if (editingId.value) {
      const updated = await updatePractice(editingId.value, payload)
      const idx = practices.value.findIndex((p) => p.id === editingId.value)
      if (idx !== -1) practices.value[idx] = updated
    } else {
      const created = await createPractice(payload)
      practices.value.push(created)
    }
    closeForm()
  } catch (e) {
    formError.value =
      e instanceof ApiError
        ? (e.detail ?? `Ошибка ${e.status}`)
        : 'Неизвестная ошибка. Попробуйте снова.'
  } finally {
    submitting.value = false
  }
}

async function toggleActive(p: Practice): Promise<void> {
  try {
    const updated = await updatePractice(p.id, { active: !p.active })
    const idx = practices.value.findIndex((x) => x.id === p.id)
    if (idx !== -1) practices.value[idx] = updated
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка обновления'
  }
}

async function remove(p: Practice): Promise<void> {
  if (!confirm(`Удалить практику «${p.name}»?`)) return
  try {
    await deletePractice(p.id)
    practices.value = practices.value.filter((x) => x.id !== p.id)
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка удаления'
  }
}

onMounted(loadPractices)
</script>

<template>
  <section class="view">
    <header class="view-header">
      <h2 class="view-title">Практики</h2>
      <Button variant="primary" size="sm" @click="openCreate">+ Добавить</Button>
    </header>

    <p v-if="listError" class="error-msg">{{ listError }}</p>

    <Spinner v-if="loading" pose="meditating" label="Загрузка практик…" />

    <EmptyState
      v-else-if="!loading && practices.length === 0 && !listError"
      pose="lounging"
      label="Практики не найдены. Создайте первую."
    />

    <!-- Card list (mobile) -->
    <div v-if="practices.length > 0" class="card-list">
      <Card
        v-for="p in practices"
        :key="p.id"
        :class="{ 'card--inactive': !p.active }"
      >
        <div class="card-main">
          <span class="card-name">{{ p.name }}</span>
          <Badge :variant="p.active ? 'active' : 'inactive'">
            {{ p.active ? 'Активна' : 'Неактивна' }}
          </Badge>
        </div>
        <div class="card-meta">
          <Badge variant="info">{{ contentTypeLabel(p.content_type) }}</Badge>
          <span class="card-hint">{{ cadenceSummary(p) }}</span>
          <span class="card-hint">Порядок: {{ p.sort_order }}</span>
        </div>
        <div class="card-actions">
          <Button
            :variant="p.active ? 'secondary' : 'ghost'"
            size="sm"
            @click="toggleActive(p)"
          >{{ p.active ? 'Выкл' : 'Вкл' }}</Button>
          <Button variant="secondary" size="sm" @click="openEdit(p)">Изменить</Button>
          <Button variant="danger" size="sm" @click="remove(p)">Удалить</Button>
        </div>
      </Card>
    </div>

    <!-- Table (wide screens) -->
    <div v-if="practices.length > 0" class="table-wrap">
      <table class="practices-table">
        <thead>
          <tr>
            <th>Название</th>
            <th>Тип</th>
            <th>Расписание</th>
            <th>Порядок</th>
            <th>Активна</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in practices" :key="p.id" :class="{ inactive: !p.active }">
            <td>{{ p.name }}</td>
            <td>{{ p.content_type }}</td>
            <td class="cadence">{{ cadenceSummary(p) }}</td>
            <td>{{ p.sort_order }}</td>
            <td>
              <button
                class="btn btn-sm"
                :class="p.active ? 'btn-active' : 'btn-inactive'"
                @click="toggleActive(p)"
              >
                {{ p.active ? 'Вкл' : 'Выкл' }}
              </button>
            </td>
            <td class="actions">
              <button class="btn btn-sm btn-secondary" @click="openEdit(p)">Изменить</button>
              <button class="btn btn-sm btn-danger" @click="remove(p)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- form modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? 'Редактировать практику' : 'Новая практика' }}</h3>
          <button class="btn-close" @click="closeForm">✕</button>
        </div>

        <form class="practice-form" @submit.prevent="submitForm">
          <p v-if="formError" class="error-msg">{{ formError }}</p>

          <Field label="Название *" :error="formErrors['name']">
            <input v-model="formData.name" type="text" maxlength="120" />
          </Field>

          <Field label="Тип контента *">
            <select v-model="formData.content_type">
              <option v-for="ct in CONTENT_TYPES" :key="ct.value" :value="ct.value">
                {{ ct.label }}
              </option>
            </select>
          </Field>

          <Field v-if="showContentField" label="Содержимое *" :error="formErrors['content']">
            <textarea v-model="formData.content" rows="3"></textarea>
          </Field>

          <Field v-if="showMediaField" label="UUID медиафайла">
            <input v-model="formData.media_asset_id" type="text" placeholder="UUID из раздела Медиа" />
          </Field>

          <div v-if="showVideoField" class="field">
            <label class="field-label">Видеофайл</label>
            <input
              ref="videoFileRef"
              type="file"
              accept="video/*"
              :disabled="videoUploading"
              @change="onVideoFileChange"
            />
            <Button
              v-if="videoFile && !videoUploading"
              type="button"
              variant="secondary"
              size="sm"
              @click="uploadVideoFile"
            >Загрузить</Button>
            <div v-if="videoUploading" class="progress-wrap">
              <div class="progress-bar" :style="{ width: `${videoProgress}%` }"></div>
              <span class="progress-label">{{ videoProgress }}%</span>
            </div>
            <p v-if="videoUploadError" class="upload-error">{{ videoUploadError }}</p>
            <p v-if="formData.media_asset_id && !videoUploading" class="upload-success">
              Загружено: {{ formData.media_asset_id }}
            </p>
          </div>

          <Field label="Тип расписания *">
            <select v-model="formData.periodicity_type">
              <option value="every_n_hours">Каждые N часов</option>
              <option value="fixed_times">Фиксированное время</option>
            </select>
          </Field>

          <template v-if="formData.periodicity_type === 'every_n_hours'">
            <Field label="Интервал (часов) *" :error="formErrors['interval_hours']">
              <input v-model.number="formData.interval_hours" type="number" min="1" />
            </Field>
            <div class="field-row">
              <Field label="Якорный час (0–23)">
                <input v-model.number="formData.anchor_hour" type="number" min="0" max="23" />
              </Field>
              <Field label="Якорные минуты (0–59)">
                <input v-model.number="formData.anchor_minute" type="number" min="0" max="59" />
              </Field>
            </div>
          </template>

          <template v-else>
            <div class="field">
              <label class="field-label">Время отправки (ЧЧ:ММ)</label>
              <div class="times-list">
                <span v-for="t in formData.schedule_times" :key="t" class="time-chip">
                  {{ t }}
                  <button type="button" class="chip-remove" @click="removeTime(t)">✕</button>
                </span>
              </div>
              <div class="time-add">
                <input
                  v-model="newTime"
                  type="text"
                  placeholder="06:00"
                  maxlength="5"
                  @keydown.enter.prevent="addTime"
                />
                <button type="button" class="btn btn-sm btn-secondary" @click="addTime">
                  Добавить
                </button>
              </div>
              <span v-if="formErrors['schedule_times']" class="field-error">
                {{ formErrors['schedule_times'] }}
              </span>
            </div>
          </template>

          <div class="field checkbox-field">
            <label>
              <input v-model="formData.active" type="checkbox" />
              Активна
            </label>
          </div>

          <div class="field-row">
            <Field label="Дата начала">
              <input v-model="formData.start_date" type="date" />
            </Field>
            <Field label="Дата окончания">
              <input v-model="formData.end_date" type="date" />
            </Field>
          </div>

          <Field label="Порядок сортировки">
            <input v-model.number="formData.sort_order" type="number" />
          </Field>

          <div class="form-actions">
            <Button type="button" variant="secondary" @click="closeForm">Отмена</Button>
            <Button type="submit" variant="primary" :disabled="submitting">
              {{ submitting ? 'Сохранение...' : editingId ? 'Сохранить' : 'Создать' }}
            </Button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<style scoped>
.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.view-title {
  font-size: var(--text-lg);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.02em;
}

.error-msg {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
}

/* Card list — shown on mobile */
.card-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.card--inactive {
  opacity: 0.6;
}

.card-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.card-name {
  font-weight: var(--font-weight-semibold);
  font-size: var(--text-base);
  flex: 1;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.card-hint {
  font-size: var(--text-xs);
  color: var(--color-hint);
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-2);
  border-top: 1px solid color-mix(in srgb, var(--color-hint) 15%, transparent);
}

/* Table — hidden on narrow screens */
.table-wrap {
  display: none;
  overflow-x: auto;
}

@media (min-width: 481px) {
  .card-list {
    display: none;
  }
  .table-wrap {
    display: block;
  }
}

.practices-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.practices-table th,
.practices-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  vertical-align: middle;
}

.practices-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}

.practices-table tr.inactive {
  opacity: 0.55;
}

.cadence {
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions {
  display: flex;
  gap: var(--space-1);
  white-space: nowrap;
}

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
}

.btn:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-sm {
  min-height: var(--tap-target);
  padding: 0 var(--space-2);
  font-size: var(--text-xs);
}

.btn-primary { background: var(--color-accent); color: var(--color-accent-text); }
.btn-secondary { background: var(--color-surface); color: var(--color-text); }
.btn-danger { background: var(--color-danger); color: #fff; }
.btn-active { background: var(--color-success); color: #fff; }
.btn-inactive { background: var(--color-inactive-bg); color: var(--color-inactive-text); }

.btn-close {
  background: none;
  border: none;
  font-size: var(--text-md);
  cursor: pointer;
  color: var(--color-hint);
  padding: var(--space-1);
  line-height: 1;
  min-height: var(--tap-target);
  min-width: var(--tap-target);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 15, 15, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--space-4);
  overflow-y: auto;
  z-index: var(--z-modal);
}

.modal {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 520px;
  box-shadow: var(--shadow-lg);
  margin-top: var(--space-2);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
}

.modal-header h3 {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.01em;
}

.practice-form {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-hint);
}

.field input,
.field select,
.field textarea {
  border: 1px solid color-mix(in srgb, var(--color-hint) 40%, transparent);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-base);
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
  box-sizing: border-box;
  font-family: var(--font-family);
  min-height: var(--tap-target);
}

.field textarea { resize: vertical; min-height: unset; }

.field-error {
  color: var(--color-danger);
  font-size: var(--text-xs);
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
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

.times-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  min-height: 1.5rem;
}

.time-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-sm);
}

.chip-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 0;
  color: var(--color-hint);
  line-height: 1;
}

.time-add {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.time-add input { width: 90px; flex-shrink: 0; }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding-top: var(--space-2);
}

.progress-wrap {
  position: relative;
  height: 1.5rem;
  background: color-mix(in srgb, var(--color-hint) 20%, transparent);
  border-radius: var(--radius-sm);
  overflow: hidden;
  margin-top: var(--space-1);
}

.progress-bar {
  position: absolute;
  inset-block: 0;
  left: 0;
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
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
}

.upload-error {
  color: var(--color-danger);
  font-size: var(--text-xs);
  margin: var(--space-1) 0 0;
}

.upload-success {
  color: var(--color-success);
  font-size: var(--text-xs);
  margin: var(--space-1) 0 0;
  word-break: break-all;
}
</style>
