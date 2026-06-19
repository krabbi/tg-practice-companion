<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit' | 'reset'
}>()

</script>

<template>
  <button
    :type="type ?? 'button'"
    :disabled="disabled || loading"
    :class="[
      'ui-btn',
      `ui-btn--${variant ?? 'primary'}`,
      `ui-btn--${size ?? 'md'}`,
      { 'ui-btn--loading': loading },
      `btn-${variant ?? 'primary'}`,
      'btn',
    ]"
    v-bind="$attrs"
  >
    <slot />
  </button>
</template>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-md);
  font-family: var(--font-family);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition:
    background-color var(--transition-fast) ease,
    transform var(--transition-fast) ease,
    opacity var(--transition-fast) ease;
  white-space: nowrap;
  min-height: var(--tap-target);
  letter-spacing: -0.01em;
}

.ui-btn:hover:not(:disabled) {
  opacity: 0.88;
}

.ui-btn:active:not(:disabled) {
  transform: scale(0.98) translateY(1px);
}

.ui-btn:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.ui-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.ui-btn--sm {
  min-height: var(--tap-target);
  padding: 0 var(--space-3);
  font-size: var(--text-sm);
}

.ui-btn--md {
  min-height: var(--tap-target);
  padding: 0 var(--space-4);
  font-size: var(--text-base);
}

.ui-btn--lg {
  min-height: calc(var(--tap-target) + 8px);
  padding: 0 var(--space-6);
  font-size: var(--text-md);
}

/* Variants */
.ui-btn--primary {
  background: var(--color-accent);
  color: var(--color-accent-text);
}

.ui-btn--secondary {
  background: var(--color-surface);
  color: var(--color-text);
}

.ui-btn--danger {
  background: var(--color-danger);
  color: #ffffff;
}

.ui-btn--ghost {
  background: transparent;
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
}

.ui-btn--ghost:hover:not(:disabled) {
  background: var(--color-info-bg);
  opacity: 1;
}
</style>
