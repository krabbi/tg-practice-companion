<script setup lang="ts">
import { ref } from 'vue'
import { ApiError } from '@/api/client'
import { getPeriodReport, type PeriodReport } from '@/api/reports'

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
  <div class="view">
    <h2>Отчёты</h2>

    <form class="report-form" @submit.prevent="fetchReport">
      <div class="field">
        <label>Дата начала *</label>
        <input v-model="dateFrom" type="date" />
        <span v-if="formErrors.dateFrom" class="field-error">{{ formErrors.dateFrom }}</span>
      </div>
      <div class="field">
        <label>Дата окончания *</label>
        <input v-model="dateTo" type="date" />
        <span v-if="formErrors.dateTo" class="field-error">{{ formErrors.dateTo }}</span>
      </div>
      <button type="submit" class="btn btn-primary" :disabled="loading">
        {{ loading ? 'Загрузка...' : 'Показать отчёт' }}
      </button>
    </form>

    <p v-if="error" class="error-msg">{{ error }}</p>

    <div v-if="report" class="report-results">
      <h3>Период: {{ report.date_from }} — {{ report.date_to }}</h3>

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
</template>

<style scoped>
h2 {
  margin-bottom: 1rem;
}

h3 {
  margin: 1.25rem 0 0.75rem;
  font-size: 0.95rem;
  color: var(--tg-theme-hint-color, #555);
}

.error-msg {
  color: #c0392b;
  background: #fdecea;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin-top: 0.75rem;
  font-size: 0.875rem;
}

.report-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-end;
  padding: 0.75rem;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
  border-radius: 8px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 150px;
}

.field label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--tg-theme-hint-color, #666);
}

.field input {
  border: 1px solid var(--tg-theme-hint-color, #ccc);
  border-radius: 6px;
  padding: 0.4rem 0.5rem;
  font-size: 0.875rem;
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #000);
  box-sizing: border-box;
}

.field-error {
  color: #c0392b;
  font-size: 0.78rem;
}

.btn {
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: opacity 0.15s;
  align-self: flex-end;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--tg-theme-button-color, #2481cc);
  color: var(--tg-theme-button-text-color, #fff);
}

.report-results {
  margin-top: 1rem;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.report-table th,
.report-table td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--tg-theme-hint-color, #ddd);
}

.report-table th {
  font-weight: 600;
  background: var(--tg-theme-secondary-bg-color, #f5f5f5);
}
</style>
