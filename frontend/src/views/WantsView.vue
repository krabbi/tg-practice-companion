<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import { listWants, createWant, updateWant, deleteWant, type Want } from '@/api/wants'

interface FormData {
  text: string
}

const EMPTY_FORM = (): FormData => ({ text: '' })

const wants = ref<Want[]>([])
const loading = ref(false)
const listError = ref('')

const showForm = ref(false)
const editingId = ref<string | null>(null)
const formData = reactive<FormData>(EMPTY_FORM())
const formError = ref('')
const formErrors = reactive<Record<string, string>>({})
const submitting = ref(false)

async function loadWants(): Promise<void> {
  loading.value = true
  listError.value = ''
  try {
    wants.value = await listWants()
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingId.value = null
  Object.assign(formData, EMPTY_FORM())
  formError.value = ''
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  showForm.value = true
}

function openEdit(w: Want): void {
  editingId.value = w.id
  Object.assign(formData, { text: w.text })
  formError.value = ''
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  showForm.value = true
}

function closeForm(): void {
  showForm.value = false
  editingId.value = null
}

function validateForm(): boolean {
  Object.keys(formErrors).forEach((k) => delete formErrors[k])
  if (!formData.text.trim()) {
    formErrors['text'] = 'Текст обязателен'
    return false
  }
  return true
}

async function submitForm(): Promise<void> {
  if (!validateForm()) return
  formError.value = ''
  submitting.value = true
  try {
    if (editingId.value) {
      const updated = await updateWant(editingId.value, { text: formData.text.trim() })
      const idx = wants.value.findIndex((w) => w.id === editingId.value)
      if (idx !== -1) wants.value[idx] = updated
    } else {
      const created = await createWant({ text: formData.text.trim() })
      wants.value.push(created)
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

async function toggleDone(w: Want): Promise<void> {
  try {
    const updated = await updateWant(w.id, { done: !w.done })
    const idx = wants.value.findIndex((x) => x.id === w.id)
    if (idx !== -1) wants.value[idx] = updated
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка обновления'
  }
}

async function remove(w: Want): Promise<void> {
  if (!confirm(`Удалить «${w.text}»?`)) return
  try {
    await deleteWant(w.id)
    wants.value = wants.value.filter((x) => x.id !== w.id)
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка удаления'
  }
}

onMounted(loadWants)
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Список «Хочу»</h2>
      <button class="btn btn-primary" @click="openCreate">+ Добавить</button>
    </div>

    <p v-if="listError" class="error-msg">{{ listError }}</p>
    <p v-if="loading" class="hint">Загрузка...</p>

    <div v-if="!loading && wants.length === 0 && !listError" class="hint">
      Список пуст. Добавьте первое желание.
    </div>

    <div v-if="wants.length > 0" class="table-wrap">
      <table class="wants-table">
        <thead>
          <tr>
            <th>Текст</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in wants" :key="w.id" :class="{ done: w.done }">
            <td class="text-cell">{{ w.text }}</td>
            <td>
              <button
                class="btn btn-sm"
                :class="w.done ? 'btn-active' : 'btn-inactive'"
                @click="toggleDone(w)"
              >
                {{ w.done ? 'Выполнено' : 'Не выполнено' }}
              </button>
            </td>
            <td class="actions">
              <button class="btn btn-sm btn-secondary" @click="openEdit(w)">Изменить</button>
              <button class="btn btn-sm btn-danger" @click="remove(w)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- form modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? 'Редактировать желание' : 'Новое желание' }}</h3>
          <button class="btn-close" @click="closeForm">✕</button>
        </div>

        <form class="item-form" @submit.prevent="submitForm">
          <p v-if="formError" class="error-msg">{{ formError }}</p>

          <div class="field">
            <label>Текст *</label>
            <textarea v-model="formData.text" rows="3" maxlength="1000"></textarea>
            <span v-if="formErrors['text']" class="field-error">{{ formErrors['text'] }}</span>
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

.wants-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.wants-table th,
.wants-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
  vertical-align: middle;
}

.wants-table th {
  font-weight: 600;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
}

.wants-table tr.done .text-cell {
  text-decoration: line-through;
  opacity: 0.6;
}

.text-cell {
  max-width: 300px;
  word-break: break-word;
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

.item-form {
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

.field textarea {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
  font-size: 0.875rem;
  background: var(--tg-theme-secondary-bg-color, #fafafa);
  color: var(--tg-theme-text-color, #000);
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
}

.field-error {
  color: #c0392b;
  font-size: 0.78rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
}
</style>
