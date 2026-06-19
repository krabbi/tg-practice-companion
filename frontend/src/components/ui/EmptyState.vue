<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  pose?: 'meditating' | 'yoga' | 'stretching' | 'lounging'
  label?: string
}>()

const catSrc = computed(() => {
  const pose = props.pose ?? 'lounging'
  return new URL(`../../assets/cats/cat-${pose}.svg`, import.meta.url).href
})

const altText = computed(() => {
  const map: Record<string, string> = {
    meditating: 'Медитирующий кот',
    yoga: 'Кот в позе йоги',
    stretching: 'Потягивающийся кот',
    lounging: 'Развалившийся кот',
  }
  return map[props.pose ?? 'lounging']
})
</script>

<template>
  <div class="ui-empty">
    <img :src="catSrc" :alt="altText" class="ui-empty__cat" />
    <p v-if="label" class="ui-empty__label">{{ label }}</p>
    <slot />
  </div>
</template>

<style scoped>
.ui-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
  text-align: center;
}

.ui-empty__cat {
  width: 96px;
  height: 96px;
  image-rendering: pixelated;
}

.ui-empty__label {
  font-size: var(--text-base);
  color: var(--color-hint);
  max-width: 260px;
  line-height: var(--leading-normal);
}
</style>
