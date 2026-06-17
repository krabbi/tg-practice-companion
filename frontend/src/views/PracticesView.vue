<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
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

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: 'question', label: 'Вопрос' },
  { value: 'text', label: 'Текст' },
  { value: 'audio', label: 'Аудио' },
  { value: 'image', label: 'Изображение' },
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
  <div class="view">
    <div class="view-header">
      <h2>Практики</h2>
      <button class="btn btn-primary" @click="openCreate">+ Добавить</button>
    </div>

    <p v-if="listError" class="error-msg">{{ listError }}</p>
    <p v-if="loading" class="hint">Загрузка...</p>

    <div v-if="!loading && practices.length === 0 && !listError" class="hint">
      Практики не найдены. Создайте первую.
    </div>

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

          <div class="field">
            <label>Название *</label>
            <input v-model="formData.name" type="text" maxlength="120" />
            <span v-if="formErrors['name']" class="field-error">{{ formErrors['name'] }}</span>
          </div>

          <div class="field">
            <label>Тип контента *</label>
            <select v-model="formData.content_type">
              <option v-for="ct in CONTENT_TYPES" :key="ct.value" :value="ct.value">
                {{ ct.label }}
              </option>
            </select>
          </div>

          <div v-if="showContentField" class="field">
            <label>Содержимое *</label>
            <textarea v-model="formData.content" rows="3"></textarea>
            <span v-if="formErrors['content']" class="field-error">{{ formErrors['content'] }}</span>
          </div>

          <div v-if="showMediaField" class="field">
            <label>UUID медиафайла</label>
            <input v-model="formData.media_asset_id" type="text" placeholder="UUID из раздела Медиа" />
          </div>

          <div class="field">
            <label>Тип расписания *</label>
            <select v-model="formData.periodicity_type">
              <option value="every_n_hours">Каждые N часов</option>
              <option value="fixed_times">Фиксированное время</option>
            </select>
          </div>

          <template v-if="formData.periodicity_type === 'every_n_hours'">
            <div class="field">
              <label>Интервал (часов) *</label>
              <input v-model.number="formData.interval_hours" type="number" min="1" />
              <span v-if="formErrors['interval_hours']" class="field-error">
                {{ formErrors['interval_hours'] }}
              </span>
            </div>
            <div class="field-row">
              <div class="field">
                <label>Якорный час (0–23)</label>
                <input v-model.number="formData.anchor_hour" type="number" min="0" max="23" />
              </div>
              <div class="field">
                <label>Якорные минуты (0–59)</label>
                <input v-model.number="formData.anchor_minute" type="number" min="0" max="59" />
              </div>
            </div>
          </template>

          <template v-else>
            <div class="field">
              <label>Время отправки (ЧЧ:ММ)</label>
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
            <div class="field">
              <label>Дата начала</label>
              <input v-model="formData.start_date" type="date" />
            </div>
            <div class="field">
              <label>Дата окончания</label>
              <input v-model="formData.end_date" type="date" />
            </div>
          </div>

          <div class="field">
            <label>Порядок сортировки</label>
            <input v-model.number="formData.sort_order" type="number" />
          </div>

          <div class="form-actions">
            <button type="button" class="btn btn-secondary" @click="closeForm">Отмена</button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? 'Сохранение...' : editingId ? 'Сохранить' : 'Создать' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.view-header h2 {
  margin: 0;
}

.hint {
  color: var(--tg-theme-hint-color, #888);
  font-size: 0.9rem;
  margin: 1rem 0;
}

.error-msg {
  color: #c0392b;
  background: #fdecea;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

.table-wrap {
  overflow-x: auto;
}

.practices-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.practices-table th,
.practices-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
  vertical-align: middle;
}

.practices-table th {
  font-weight: 600;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
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
  gap: 0.4rem;
  white-space: nowrap;
}

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

.btn-active {
  background: #27ae60;
  color: #fff;
}

.btn-inactive {
  background: #bdc3c7;
  color: #333;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--tg-theme-hint-color, #888);
  padding: 0.25rem;
  line-height: 1;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 1rem;
  overflow-y: auto;
  z-index: 100;
}

.modal {
  background: var(--tg-theme-bg-color, #fff);
  border-radius: 12px;
  width: 100%;
  max-width: 520px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18);
  margin-top: 0.5rem;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
}

/* Form */
.practice-form {
  padding: 1rem 1.25rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

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

.field input,
.field select,
.field textarea {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
  font-size: 0.875rem;
  background: var(--tg-theme-secondary-bg-color, #fafafa);
  color: var(--tg-theme-text-color, #000);
  width: 100%;
  box-sizing: border-box;
}

.field textarea {
  resize: vertical;
}

.field-error {
  color: #c0392b;
  font-size: 0.78rem;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
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

.times-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  min-height: 1.5rem;
}

.time-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--tg-theme-secondary-bg-color, #e8f4fd);
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  font-size: 0.8rem;
}

.chip-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.7rem;
  padding: 0;
  color: var(--tg-theme-hint-color, #888);
  line-height: 1;
}

.time-add {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.time-add input {
  width: 90px;
  flex-shrink: 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
}
</style>
