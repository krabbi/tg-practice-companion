<script setup lang="ts">
defineProps<{
  variant?: 'active' | 'inactive' | 'success' | 'warning' | 'info' | 'danger'
}>()
</script>

<template>
  <span :class="['ui-badge', `ui-badge--${variant ?? 'info'}`]">
    <slot />
  </span>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  border-radius: var(--radius-sm);
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-weight-semibold);
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.ui-badge--active {
  background: var(--color-active-bg);
  color: var(--color-active-text);
}

.ui-badge--inactive {
  background: var(--color-inactive-bg);
  color: var(--color-inactive-text);
}

.ui-badge--success {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.ui-badge--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.ui-badge--info {
  background: var(--color-info-bg);
  color: var(--color-accent);
}

.ui-badge--danger {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
</style>
