<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ApiError } from '@/api/client'
import { listJournal, type JournalEntry, type JournalListParams } from '@/api/journal'
import { listPractices, type Practice } from '@/api/practices'
import Card from '@/components/ui/Card.vue'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Spinner from '@/components/ui/Spinner.vue'

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
  <section class="view">
    <h2 class="view-title">Дневник</h2>

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
        <Button variant="primary" size="sm" @click="applyFilters">Применить</Button>
        <Button variant="secondary" size="sm" @click="resetFilters">Сбросить</Button>
      </div>
    </div>

    <p v-if="listError" class="error-msg">{{ listError }}</p>

    <Spinner v-if="loading" pose="meditating" label="Загрузка записей…" />

    <EmptyState
      v-else-if="!loading && entries.length === 0 && !listError"
      pose="lounging"
      label="Записей не найдено."
    />

    <!-- Card list (mobile) -->
    <div v-if="entries.length > 0" class="card-list">
      <Card
        v-for="entry in entries"
        :key="entry.id"
        :interactive="true"
        @click="openDetail(entry)"
      >
        <div class="card-row">
          <span class="card-date">{{ formatDate(entry.created_at) }}</span>
          <Badge variant="info">{{ entry.source === 'voice' ? 'Голос' : 'Текст' }}</Badge>
          <template v-if="entry.self_assessment !== null">
            <span>{{ entry.self_assessment.leads_to_goals ? '✅' : '❌' }}</span>
          </template>
          <span v-else class="card-hint">—</span>
        </div>
        <div v-if="entry.practice_name" class="card-practice">{{ entry.practice_name }}</div>
        <p class="card-text">{{ truncate(entry.text) }}</p>
      </Card>
    </div>

    <!-- Table (wide screens) -->
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
      <Button variant="secondary" size="sm" :disabled="page === 1" @click="prevPage">
        ← Назад
      </Button>
      <span class="page-info">Страница {{ page }} / {{ totalPages() }}</span>
      <Button
        variant="secondary"
        size="sm"
        :disabled="page * PAGE_SIZE >= total"
        @click="nextPage"
      >
        Вперёд →
      </Button>
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
  </section>
</template>

<style scoped>
.view-title {
  font-size: var(--text-lg);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-4);
}

.error-msg {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: flex-end;
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 130px;
}

.filter-field label {
  font-size: var(--text-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-hint);
}

.filter-field input,
.filter-field select {
  border: 1px solid color-mix(in srgb, var(--color-hint) 40%, transparent);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  background: var(--color-bg);
  color: var(--color-text);
  box-sizing: border-box;
  font-family: var(--font-family);
  min-height: var(--tap-target);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
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

.card-practice {
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-hint);
}

.card-text {
  font-size: var(--text-base);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-hint { color: var(--color-hint); font-size: var(--text-sm); }

/* Table */
.journal-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.journal-table th,
.journal-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  vertical-align: top;
}

.journal-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  font-size: var(--text-xs);
}

.clickable-row { cursor: pointer; }
.clickable-row:hover { background: var(--color-surface); }

.col-date { white-space: nowrap; font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
.col-text { max-width: 280px; word-break: break-word; }
.col-assess { text-align: center; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-4);
  justify-content: center;
}

.page-info {
  font-size: var(--text-sm);
  color: var(--color-hint);
  font-variant-numeric: tabular-nums;
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
  border-radius: var(--radius-sm);
}

.modal-body { padding: var(--space-4); }

.detail-list {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-1) var(--space-4);
  margin: 0;
  font-size: var(--text-sm);
}

.detail-list dt {
  font-weight: var(--font-weight-semibold);
  color: var(--color-hint);
  white-space: nowrap;
}

.detail-list dd {
  margin: 0;
  word-break: break-word;
}

.entry-text { white-space: pre-wrap; }
</style>
