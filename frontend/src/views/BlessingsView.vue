<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import {
  listBlessings,
  createBlessing,
  updateBlessing,
  deleteBlessing,
  reorderBlessings,
  type Blessing,
} from '@/api/blessings'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Field from '@/components/ui/Field.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'

interface FormData {
  text: string
  active: boolean
}

const EMPTY_FORM = (): FormData => ({ text: '', active: true })

const blessings = ref<Blessing[]>([])
const loading = ref(false)
const listError = ref('')

const showForm = ref(false)
const editingId = ref<string | null>(null)
const formData = reactive<FormData>(EMPTY_FORM())
const formError = ref('')
const formErrors = reactive<Record<string, string>>({})
const submitting = ref(false)

async function loadBlessings(): Promise<void> {
  loading.value = true
  listError.value = ''
  try {
    blessings.value = await listBlessings()
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

function openEdit(b: Blessing): void {
  editingId.value = b.id
  Object.assign(formData, { text: b.text, active: b.active })
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
      const updated = await updateBlessing(editingId.value, {
        text: formData.text.trim(),
        active: formData.active,
      })
      const idx = blessings.value.findIndex((b) => b.id === editingId.value)
      if (idx !== -1) blessings.value[idx] = updated
    } else {
      const created = await createBlessing({ text: formData.text.trim(), active: formData.active })
      blessings.value.push(created)
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

async function toggleActive(b: Blessing): Promise<void> {
  try {
    const updated = await updateBlessing(b.id, { active: !b.active })
    const idx = blessings.value.findIndex((x) => x.id === b.id)
    if (idx !== -1) blessings.value[idx] = updated
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка обновления'
  }
}

async function remove(b: Blessing): Promise<void> {
  if (!confirm(`Удалить «${b.text}»?`)) return
  try {
    await deleteBlessing(b.id)
    blessings.value = blessings.value.filter((x) => x.id !== b.id)
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка удаления'
  }
}

async function move(idx: number, direction: -1 | 1): Promise<void> {
  const target = idx + direction
  if (target < 0 || target >= blessings.value.length) return

  const reordered = [...blessings.value]
  ;[reordered[idx], reordered[target]] = [reordered[target], reordered[idx]]

  listError.value = ''
  try {
    blessings.value = await reorderBlessings(reordered.map((b) => b.id))
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка изменения порядка'
  }
}

onMounted(loadBlessings)
</script>

<template>
  <section class="view">
    <header class="view-header">
      <h2 class="view-title">Утренние напутствия</h2>
      <Button variant="primary" size="sm" @click="openCreate">+ Добавить</Button>
    </header>

    <p v-if="listError" class="error-msg">{{ listError }}</p>

    <Spinner v-if="loading" pose="meditating" label="Загрузка напутствий…" />

    <EmptyState
      v-else-if="!loading && blessings.length === 0 && !listError"
      pose="lounging"
      label="Напутствия не найдены. Добавьте первое."
    />

    <!-- Card list (mobile) -->
    <div v-if="blessings.length > 0" class="card-list">
      <Card
        v-for="(b, idx) in blessings"
        :key="b.id"
        :class="{ 'card--inactive': !b.active }"
      >
        <div class="card-main">
          <div class="order-controls-card">
            <button
              class="btn-order"
              :disabled="idx === 0"
              title="Переместить вверх"
              @click="move(idx, -1)"
            >▲</button>
            <span class="order-num">{{ b.rotation_order }}</span>
            <button
              class="btn-order"
              :disabled="idx === blessings.length - 1"
              title="Переместить вниз"
              @click="move(idx, 1)"
            >▼</button>
          </div>
          <p class="card-text">{{ b.text }}</p>
          <Badge :variant="b.active ? 'active' : 'inactive'">
            {{ b.active ? 'Вкл' : 'Выкл' }}
          </Badge>
        </div>
        <div class="card-actions">
          <Button variant="secondary" size="sm" @click="openEdit(b)">Изменить</Button>
          <Button variant="danger" size="sm" @click="remove(b)">Удалить</Button>
        </div>
      </Card>
    </div>

    <!-- Table (wide screens) -->
    <div v-if="blessings.length > 0" class="table-wrap">
      <table class="blessings-table">
        <thead>
          <tr>
            <th class="order-col">Порядок</th>
            <th>Текст</th>
            <th>Активно</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(b, idx) in blessings" :key="b.id" :class="{ inactive: !b.active }">
            <td class="order-col">
              <div class="order-controls">
                <button
                  class="btn-order"
                  :disabled="idx === 0"
                  title="Переместить вверх"
                  @click="move(idx, -1)"
                >▲</button>
                <span class="order-num">{{ b.rotation_order }}</span>
                <button
                  class="btn-order"
                  :disabled="idx === blessings.length - 1"
                  title="Переместить вниз"
                  @click="move(idx, 1)"
                >▼</button>
              </div>
            </td>
            <td class="text-cell">{{ b.text }}</td>
            <td>
              <button
                class="btn btn-sm"
                :class="b.active ? 'btn-active' : 'btn-inactive'"
                @click="toggleActive(b)"
              >
                {{ b.active ? 'Вкл' : 'Выкл' }}
              </button>
            </td>
            <td class="actions">
              <button class="btn btn-sm btn-secondary" @click="openEdit(b)">Изменить</button>
              <button class="btn btn-sm btn-danger" @click="remove(b)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- form modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? 'Редактировать напутствие' : 'Новое напутствие' }}</h3>
          <button class="btn-close" @click="closeForm">✕</button>
        </div>

        <form class="item-form" @submit.prevent="submitForm">
          <p v-if="formError" class="error-msg">{{ formError }}</p>

          <Field label="Текст *" :error="formErrors['text']">
            <textarea v-model="formData.text" rows="3" maxlength="1000"></textarea>
          </Field>

          <div class="checkbox-field">
            <label>
              <input v-model="formData.active" type="checkbox" />
              Активно
            </label>
          </div>

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

/* Card list */
.card-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.card--inactive { opacity: 0.6; }

.card-main {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.card-text {
  flex: 1;
  font-size: var(--text-base);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.order-controls-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.order-controls {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.order-num {
  min-width: 1.5rem;
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-hint);
  font-variant-numeric: tabular-nums;
}

.btn-order {
  background: none;
  border: 1px solid color-mix(in srgb, var(--color-hint) 40%, transparent);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-2);
  line-height: 1;
  color: var(--color-text);
  min-height: var(--tap-target);
  min-width: var(--tap-target);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-order:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid color-mix(in srgb, var(--color-hint) 15%, transparent);
}

/* Table */
.table-wrap { display: none; overflow-x: auto; }

@media (min-width: 481px) {
  .card-list { display: none; }
  .table-wrap { display: block; }
}

.blessings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.blessings-table th,
.blessings-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  vertical-align: middle;
}

.blessings-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  font-size: var(--text-xs);
}

.blessings-table tr.inactive { opacity: 0.55; }
.order-col { width: 80px; }
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

.item-form {
  padding: var(--space-4);
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
  padding-top: var(--space-2);
}
</style>
