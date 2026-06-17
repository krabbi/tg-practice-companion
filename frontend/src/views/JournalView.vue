<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import { listJournal, type JournalEntry, type JournalListParams } from '@/api/journal'
import { listPractices, type Practice } from '@/api/practices'

const PAGE_SIZE = 20

const entries = ref<JournalEntry[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const listError = ref('')

const filterDateFrom = ref('')
const filterDateTo = ref('')
const filterPracticeId = ref('')

const practices = ref<Practice[]>([])

const selected = ref<JournalEntry | null>(null)

async function load(): Promise<void> {
  loading.value = true
  listError.value = ''
  const params: JournalListParams = {
    page: page.value,
    page_size: PAGE_SIZE,
  }
  if (filterDateFrom.value) params.date_from = filterDateFrom.value
  if (filterDateTo.value) params.date_to = filterDateTo.value
  if (filterPracticeId.value) params.practice_id = filterPracticeId.value
  try {
    const res = await listJournal(params)
    entries.value = res.items
    total.value = res.total
  } catch (e) {
    listError.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

async function applyFilters(): Promise<void> {
  page.value = 1
  await load()
}

function resetFilters(): void {
  filterDateFrom.value = ''
  filterDateTo.value = ''
  filterPracticeId.value = ''
  page.value = 1
  load()
}

async function prevPage(): Promise<void> {
  if (page.value > 1) {
    page.value--
    await load()
  }
}

async function nextPage(): Promise<void> {
  if (page.value * PAGE_SIZE < total.value) {
    page.value++
    await load()
  }
}

function totalPages(): number {
  return Math.max(1, Math.ceil(total.value / PAGE_SIZE))
}

function formatDate(iso: string): string {
  return iso.replace('T', ' ').slice(0, 16)
}

function truncate(text: string, max = 80): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}

function openDetail(entry: JournalEntry): void {
  selected.value = entry
}

function closeDetail(): void {
  selected.value = null
}

onMounted(async () => {
  const [, practicesResult] = await Promise.allSettled([load(), listPractices()])
  if (practicesResult.status === 'fulfilled') {
    practices.value = practicesResult.value
  }
})
</script>

<template>
  <div class="view">
    <h2>Дневник</h2>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-field">
        <label>С</label>
        <input v-model="filterDateFrom" type="date" />
      </div>
      <div class="filter-field">
        <label>По</label>
        <input v-model="filterDateTo" type="date" />
      </div>
      <div class="filter-field">
        <label>Практика</label>
        <select v-model="filterPracticeId">
          <option value="">Все практики</option>
          <option v-for="p in practices" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
      <div class="filter-actions">
        <button class="btn btn-primary btn-sm" @click="applyFilters">Применить</button>
        <button class="btn btn-secondary btn-sm" @click="resetFilters">Сбросить</button>
      </div>
    </div>

    <p v-if="listError" class="error-msg">{{ listError }}</p>
    <p v-if="loading" class="hint">Загрузка...</p>

    <div v-if="!loading && entries.length === 0 && !listError" class="hint">
      Записей не найдено.
    </div>

    <div v-if="entries.length > 0" class="table-wrap">
      <table class="journal-table">
        <thead>
          <tr>
            <th>Дата и время</th>
            <th>Практика</th>
            <th>Источник</th>
            <th>Текст</th>
            <th>Оценка</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.id"
            class="clickable-row"
            @click="openDetail(entry)"
          >
            <td class="col-date">{{ formatDate(entry.created_at) }}</td>
            <td>{{ entry.practice_name ?? '—' }}</td>
            <td>{{ entry.source === 'voice' ? 'Голос' : 'Текст' }}</td>
            <td class="col-text">{{ truncate(entry.text) }}</td>
            <td class="col-assess">
              <template v-if="entry.self_assessment !== null">
                {{ entry.self_assessment.leads_to_goals ? '✅' : '❌' }}
              </template>
              <template v-else>—</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > PAGE_SIZE" class="pagination">
      <button class="btn btn-secondary btn-sm" :disabled="page === 1" @click="prevPage">
        ← Назад
      </button>
      <span class="page-info">Страница {{ page }} / {{ totalPages() }}</span>
      <button
        class="btn btn-secondary btn-sm"
        :disabled="page * PAGE_SIZE >= total"
        @click="nextPage"
      >
        Вперёд →
      </button>
    </div>

    <!-- Detail modal -->
    <div v-if="selected" class="modal-overlay" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-header">
          <h3>Запись дневника</h3>
          <button class="btn-close" @click="closeDetail">✕</button>
        </div>
        <div class="modal-body">
          <dl class="detail-list">
            <dt>Дата и время</dt>
            <dd>{{ formatDate(selected.created_at) }}</dd>

            <dt>Практика</dt>
            <dd>{{ selected.practice_name ?? '—' }}</dd>

            <dt>Источник</dt>
            <dd>{{ selected.source === 'voice' ? 'Голос' : 'Текст' }}</dd>

            <dt>Текст</dt>
            <dd class="entry-text">{{ selected.text }}</dd>

            <dt>Самооценка</dt>
            <dd v-if="selected.self_assessment !== null">
              {{ selected.self_assessment.leads_to_goals ? '✅ Ведёт к целям' : '❌ Не ведёт к целям' }}
              ({{ selected.self_assessment.set_via }})
            </dd>
            <dd v-else>—</dd>
          </dl>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
h2 {
  margin-bottom: 1rem;
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

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-end;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
  border-radius: 8px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 130px;
}

.filter-field label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--tg-theme-hint-color, #666);
}

.filter-field input,
.filter-field select {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.4rem 0.5rem;
  font-size: 0.85rem;
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #000);
  box-sizing: border-box;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.table-wrap {
  overflow-x: auto;
}

.journal-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.journal-table th,
.journal-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
  vertical-align: top;
}

.journal-table th {
  font-weight: 600;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: var(--tg-theme-secondary-bg-color, #f9f9f9);
}

.col-date {
  white-space: nowrap;
  font-size: 0.8rem;
}

.col-text {
  max-width: 280px;
  word-break: break-word;
}

.col-assess {
  text-align: center;
  font-size: 1rem;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
  justify-content: center;
}

.page-info {
  font-size: 0.875rem;
  color: var(--tg-theme-hint-color, #666);
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
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 0.3rem 0.7rem;
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

.modal-body {
  padding: 1rem 1.25rem 1.25rem;
}

.detail-list {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.4rem 1rem;
  margin: 0;
  font-size: 0.875rem;
}

.detail-list dt {
  font-weight: 600;
  color: var(--tg-theme-hint-color, #666);
  white-space: nowrap;
}

.detail-list dd {
  margin: 0;
  word-break: break-word;
}

.entry-text {
  white-space: pre-wrap;
}
</style>
