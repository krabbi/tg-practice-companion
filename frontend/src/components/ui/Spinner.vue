<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  pose?: 'meditating' | 'stretching'
  label?: string
}>()

const catSrc = computed(() => {
  const pose = props.pose ?? 'meditating'
  return new URL(`../../assets/cats/cat-${pose}.svg`, import.meta.url).href
})

const altText = computed(() => {
  return props.pose === 'stretching' ? 'Потягивающийся кот' : 'Медитирующий кот'
})
</script>

<template>
  <div class="ui-spinner">
    <img :src="catSrc" :alt="altText" class="ui-spinner__cat" />
    <p v-if="label" class="ui-spinner__label">{{ label }}</p>
  </div>
</template>

<style scoped>
.ui-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
}

.ui-spinner__cat {
  width: 72px;
  height: 72px;
  image-rendering: pixelated;
  animation: cat-pulse 2s ease-in-out infinite;
}

.ui-spinner__label {
  font-size: var(--text-base);
  color: var(--color-hint);
}

@keyframes cat-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(0.95); }
}
</style>
