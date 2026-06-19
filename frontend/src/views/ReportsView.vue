<script setup lang="ts">
import { ref } from 'vue'
import { ApiError } from '@/api/client'
import { getPeriodReport, type PeriodReport } from '@/api/reports'
import Button from '@/components/ui/Button.vue'
import Field from '@/components/ui/Field.vue'

const dateFrom = ref('')
const dateTo = ref('')
const loading = ref(false)
const error = ref('')
const report = ref<PeriodReport | null>(null)
const formErrors = ref<{ dateFrom?: string; dateTo?: string }>({})

function validate(): boolean {
  formErrors.value = {}
  if (!dateFrom.value) {
    formErrors.value.dateFrom = 'Укажите дату начала'
    return false
  }
  if (!dateTo.value) {
    formErrors.value.dateTo = 'Укажите дату окончания'
    return false
  }
  if (dateTo.value < dateFrom.value) {
    formErrors.value.dateTo = 'Дата окончания должна быть не раньше даты начала'
    return false
  }
  return true
}

async function fetchReport(): Promise<void> {
  if (!validate()) return
  loading.value = true
  error.value = ''
  report.value = null
  try {
    report.value = await getPeriodReport(dateFrom.value, dateTo.value)
  } catch (e) {
    error.value = e instanceof ApiError ? (e.detail ?? e.message) : 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function leadsPercent(r: PeriodReport): string {
  if (r.n_total === 0) return '—'
  return `${Math.round((r.n_leads / r.n_total) * 100)}%`
}
</script>

<template>
  <section class="view">
    <h2 class="view-title">Отчёты</h2>

    <form class="report-form" @submit.prevent="fetchReport">
      <Field label="Дата начала *" :error="formErrors.dateFrom">
        <input v-model="dateFrom" type="date" />
      </Field>
      <Field label="Дата окончания *" :error="formErrors.dateTo">
        <input v-model="dateTo" type="date" />
      </Field>
      <Button type="submit" variant="primary" :disabled="loading">
        {{ loading ? 'Загрузка...' : 'Показать отчёт' }}
      </Button>
    </form>

    <p v-if="error" class="error-msg">{{ error }}</p>

    <div v-if="report" class="report-results">
      <h3 class="report-period">Период: {{ report.date_from }} — {{ report.date_to }}</h3>

      <!-- Stats cards (mobile) -->
      <div class="stats-cards">
        <div class="stat-card">
          <span class="stat-value">{{ report.n_total }}</span>
          <span class="stat-label">Всего записей в дневнике</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ report.n_leads }} <small>({{ leadsPercent(report) }})</small></span>
          <span class="stat-label">Мыслей, ведущих к целям</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ report.n_practices }}</span>
          <span class="stat-label">Практик отправлено</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ report.n_good_deeds }}</span>
          <span class="stat-label">Добрых дел</span>
        </div>
      </div>

      <!-- Table (wide screens) -->
      <div class="table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th>Показатель</th>
              <th>Значение</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Всего записей в дневнике</td>
              <td>{{ report.n_total }}</td>
            </tr>
            <tr>
              <td>Мыслей, ведущих к целям</td>
              <td>{{ report.n_leads }} ({{ leadsPercent(report) }})</td>
            </tr>
            <tr>
              <td>Практик отправлено</td>
              <td>{{ report.n_practices }}</td>
            </tr>
            <tr>
              <td>Добрых дел</td>
              <td>{{ report.n_good_deeds }}</td>
            </tr>
          </tbody>
        </table>
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
  margin-top: var(--space-3);
  font-size: var(--text-sm);
}

.report-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: flex-end;
  padding: var(--space-4);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
}

.report-results { margin-top: var(--space-5); }

.report-period {
  font-size: var(--text-sm);
  color: var(--color-hint);
  margin-bottom: var(--space-4);
  font-weight: var(--font-weight-medium);
}

/* Stats cards — always shown, extra on mobile */
.stats-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

@media (min-width: 481px) {
  .stats-cards { display: none; }
}

.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: var(--font-weight-bold);
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
}

.stat-value small {
  font-size: var(--text-sm);
  font-weight: var(--font-weight-regular);
  color: var(--color-hint);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-hint);
  line-height: var(--leading-normal);
}

/* Table */
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.report-table th,
.report-table td {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
}

.report-table th {
  font-weight: var(--font-weight-semibold);
  background: var(--color-surface);
  color: var(--color-hint);
  font-size: var(--text-xs);
}

.report-table td:last-child {
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
}
</style>
