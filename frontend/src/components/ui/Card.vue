<script setup lang="ts">
defineProps<{
  interactive?: boolean
}>()
</script>

<template>
  <article :class="['ui-card', { 'ui-card--interactive': interactive }]">
    <slot />
  </article>
</template>

<style scoped>
.ui-card {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid color-mix(in srgb, var(--color-hint) 20%, transparent);
  padding: var(--space-4);
  transition: box-shadow var(--transition-fast) ease;
}

.ui-card--interactive {
  cursor: pointer;
}

.ui-card--interactive:hover {
  box-shadow: var(--shadow-md);
}

.ui-card--interactive:active {
  transform: scale(0.995);
}
</style>
