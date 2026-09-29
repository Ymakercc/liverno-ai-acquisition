<script setup lang="ts">
import type { FunnelNode } from '@/types/dashboard'

defineProps<{ nodes: FunnelNode[] }>()
const emit = defineEmits<{ (event: 'navigate', to: string): void }>()

function handleClick(node: FunnelNode): void {
  if (node.to) emit('navigate', node.to)
}
</script>

<template>
  <section class="funnel app-card">
    <header class="funnel__head">
      <h3 class="funnel__title">
        自动获客流程
      </h3>
      <span class="funnel__sub">从企业发现到商机的当前链路数量</span>
    </header>

    <div class="funnel__flow">
      <template
        v-for="(node, index) in nodes"
        :key="node.key"
      >
        <div
          v-if="index > 0"
          class="funnel__arrow"
          aria-hidden="true"
        >
          →
        </div>
        <div
          class="funnel__node"
          :class="{ 'is-clickable': !!node.to, 'is-ai': node.source === 'ai' }"
          @click="handleClick(node)"
        >
          <div class="funnel__value num">
            {{ node.value }}
          </div>
          <div class="funnel__label">
            {{ node.label }}
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.funnel {
  padding: var(--space-xl);
}

.funnel__head {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.funnel__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.funnel__sub {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* 纯 CSS 横向流程，不引图表库（CLAUDE.md 5.3） */
.funnel__flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: stretch;
  margin-top: 18px;
}

.funnel__node {
  flex: 1 1 96px;
  min-width: 96px;
  padding: 14px 10px;
  text-align: center;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-base);
}

.funnel__node.is-clickable {
  cursor: pointer;
}

.funnel__node.is-clickable:hover {
  border-color: var(--color-primary);
}

.funnel__node.is-ai {
  background: var(--color-ai-bg);
  border-color: var(--color-ai-border);
}

.funnel__value {
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-text-primary);
}

.funnel__node.is-ai .funnel__value {
  color: var(--color-ai-text);
}

.funnel__label {
  margin-top: 4px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.funnel__arrow {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  font-size: var(--font-size-base);
  color: var(--color-text-placeholder);
}
</style>
