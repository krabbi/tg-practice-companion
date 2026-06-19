<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import { listWants, createWant, updateWant, deleteWant, type Want } from '@/api/wants'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Field from '@/components/ui/Field.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'

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
  <section class="view">
    <header class="view-header">
      <h2 class="view-title">Список «Хочу»</h2>
      <Button variant="primary" size="sm" @click="openCreate">+ Добавить</Button>
    </header>

    <p v-if="listError" class="error-msg">{{ listError }}</p>

    <Spinner v-if="loading" pose="meditating" label="Загрузка…" />

    <EmptyState
      v-else-if="!loading && wants.length === 0 && !listError"
      pose="lounging"
      label="Список пуст. Добавьте первое желание."
    />

    <!-- Card list (mobile) -->
    <div v-if="wants.length > 0" class="card-list">
      <Card v-for="w in wants" :key="w.id" :class="{ 'card--done': w.done }">
        <div class="card-main">
          <p class="card-text" :class="{ 'card-text--done': w.done }">{{ w.text }}</p>
          <Badge :variant="w.done ? 'success' : 'inactive'">
            {{ w.done ? 'Выполнено' : 'Не выполнено' }}
          </Badge>
        </div>
        <div class="card-actions">
          <Button
            :variant="w.done ? 'secondary' : 'ghost'"
            size="sm"
            @click="toggleDone(w)"
          >{{ w.done ? 'Вернуть' : 'Выполнено' }}</Button>
          <Button variant="secondary" size="sm" @click="openEdit(w)">Изменить</Button>
          <Button variant="danger" size="sm" @click="remove(w)">Удалить</Button>
        </div>
      </Card>
    </div>

    <!-- Table (wide screens) -->
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

          <Field label="Текст *" :error="formErrors['text']">
            <textarea v-model="formData.text" rows="3" maxlength="1000"></textarea>
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

/* Cards */
.card-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.card-text {
  flex: 1;
  font-size: var(--text-base);
  word-break: break-word;
}

.card-text--done {
  text-decoration: line-through;
  opacity: 0.6;
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-2);
  border-top: 1px solid color-mix(in srgb, var(--color-hint) 15%, transparent);
}

/* Table */
.wants-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.wants-table th,
.wants-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  vertical-align: middle;
}

.wants-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  font-size: var(--text-xs);
}

.wants-table tr.done .text-cell {
  text-decoration: line-through;
  opacity: 0.6;
}

.text-cell { max-width: 300px; word-break: break-word; }
.actions { display: flex; gap: var(--space-1); white-space: nowrap; }

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
.btn-sm { min-height: var(--tap-target); padding: 0 var(--space-2); font-size: var(--text-xs); }
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
  min-height: var(--tap-target);
  min-width: var(--tap-target);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
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

.item-form {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding-top: var(--space-2);
}
</style>
