<script setup lang="ts">
defineProps<{
  open: boolean
  title?: string
}>()

const emit = defineEmits<{
  close: []
}>()

function onOverlayClick(): void {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="ui-modal-overlay" @click.self="onOverlayClick">
      <div class="ui-modal" role="dialog" :aria-label="title">
        <div v-if="title || $slots.header" class="ui-modal__header">
          <slot name="header">
            <h3 class="ui-modal__title">{{ title }}</h3>
          </slot>
          <button class="ui-modal__close btn-close" @click="emit('close')" aria-label="Закрыть">✕</button>
        </div>
        <div class="ui-modal__body">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ui-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 15, 15, 0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--space-4);
  overflow-y: auto;
  z-index: var(--z-modal);
}

.ui-modal {
  background: var(--color-bg);
  border-radius: var(--radius-xl);
  width: 100%;
  max-width: 520px;
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-lg), var(--glass-inset);
  margin-top: var(--space-2);
}

.ui-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5) var(--space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
}

.ui-modal__title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.01em;
}

.ui-modal__close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--color-hint);
  padding: var(--space-1);
  line-height: 1;
  border-radius: var(--radius-sm);
  min-width: var(--tap-target);
  min-height: var(--tap-target);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--transition-fast) ease;
}

.ui-modal__close:hover {
  background: var(--color-surface);
}

.ui-modal__body {
  padding: var(--space-4) var(--space-5) var(--space-5);
}
</style>
