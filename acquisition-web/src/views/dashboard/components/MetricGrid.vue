<script setup lang="ts">
import type { CoreMetric } from '@/types/dashboard'

defineProps<{ metrics: CoreMetric[] }>()
const emit = defineEmits<{ (event: 'navigate', to: string): void }>()

function handleClick(metric: CoreMetric): void {
  if (metric.to) emit('navigate', metric.to)
}
</script>

<template>
  <div class="metric-grid">
    <div
      v-for="metric in metrics"
      :key="metric.key"
      class="metric-grid__item app-card"
      :class="{ 'is-clickable': !!metric.to }"
      @click="handleClick(metric)"
    >
      <div class="metric-grid__label">
        <span>{{ metric.label }}</span>
        <span
          v-if="metric.source === 'ai'"
          class="metric-grid__ai"
        >AI</span>
      </div>
      <div class="metric-grid__value num">
        {{ metric.value }}
      </div>
      <div class="metric-grid__hint">
        {{ metric.hint }}
      </div>
    </div>
  </div>
</template>

<style scoped>
/**
 * 8 张指标卡固定列数排布，保证每行排满、不出现落单卡片：
 *   ≥1760 → 8 列（一行）
 *   1100~1759 → 4 列（两行）
 *   <1100 → 2 列（四行）
 */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-base);
}

@media (min-width: 1760px) {
  .metric-grid {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
}

@media (max-width: 1099px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.metric-grid__item {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
}

.metric-grid__item.is-clickable {
  cursor: pointer;
}

.metric-grid__item.is-clickable:hover {
  border-color: var(--color-primary);
}

.metric-grid__label {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* AI 产出标识，仅用于 AI 判断类指标（CLAUDE.md 7.3） */
.metric-grid__ai {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

.metric-grid__value {
  margin-top: 8px;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-text-primary);
}

.metric-grid__hint {
  margin-top: auto;
  padding-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}
</style>
