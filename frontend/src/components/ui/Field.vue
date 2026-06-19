<script setup lang="ts">
defineProps<{
  label?: string
  error?: string
  hint?: string
}>()
</script>

<template>
  <div class="ui-field">
    <label v-if="label" class="ui-field__label">{{ label }}</label>
    <div class="ui-field__control">
      <slot />
    </div>
    <span v-if="error" class="ui-field__error">{{ error }}</span>
    <span v-else-if="hint" class="ui-field__hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.ui-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.ui-field__label {
  font-size: var(--text-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-hint);
  letter-spacing: -0.01em;
}

.ui-field__control :deep(input),
.ui-field__control :deep(select),
.ui-field__control :deep(textarea) {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--color-hint) 40%, transparent);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-base);
  font-family: var(--font-family);
  background: var(--color-surface);
  color: var(--color-text);
  min-height: var(--tap-target);
  transition: border-color var(--transition-fast) ease;
}

.ui-field__control :deep(input:focus),
.ui-field__control :deep(select:focus),
.ui-field__control :deep(textarea:focus) {
  outline: none;
  border-color: var(--color-accent);
}

.ui-field__control :deep(textarea) {
  min-height: unset;
  resize: vertical;
}

.ui-field__error {
  font-size: var(--text-xs);
  color: var(--color-danger);
}

.ui-field__hint {
  font-size: var(--text-xs);
  color: var(--color-hint);
}
</style>
