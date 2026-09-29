<script setup lang="ts">
import { computed } from 'vue'
import type { PendingTask } from '@/types/dashboard'

const props = defineProps<{ tasks: PendingTask[] }>()
const emit = defineEmits<{ (event: 'navigate', to: string): void }>()

const total = computed<number>(() => props.tasks.reduce((sum, item) => sum + item.count, 0))
</script>

<template>
  <section class="pending app-card">
    <header class="pending__head">
      <h3 class="pending__title">
        今日待处理
      </h3>
      <span class="pending__total num">共 {{ total }} 项</span>
    </header>

    <ul
      v-if="tasks.length"
      class="pending__list"
    >
      <li
        v-for="task in tasks"
        :key="task.key"
        class="pending__item"
        @click="emit('navigate', task.to)"
      >
        <span
          class="pending__dot"
          :class="`is-${task.level}`"
        />
        <span class="pending__label">{{ task.label }}</span>
        <span
          class="pending__count num"
          :class="`is-${task.level}`"
        >{{ task.count }}</span>
        <el-icon class="pending__arrow">
          <ArrowRight />
        </el-icon>
      </li>
    </ul>

    <el-empty
      v-else
      description="今日没有需要人工处理的事项"
      :image-size="72"
    />
  </section>
</template>

<style scoped>
.pending {
  display: flex;
  flex-direction: column;
  padding: var(--space-xl);
}

.pending__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.pending__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.pending__total {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.pending__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: space-between;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.pending__item {
  display: flex;
  flex: 1;
  gap: 10px;
  align-items: center;
  min-height: 44px;
  padding: 10px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
}

.pending__item:last-child {
  border-bottom: none;
}

.pending__item:hover {
  background: var(--color-bg);
}

.pending__dot {
  flex: 0 0 6px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.pending__dot.is-danger {
  background: var(--color-danger);
}

.pending__dot.is-warning {
  background: var(--color-warning);
}

.pending__dot.is-info {
  background: var(--color-info-main);
}

.pending__label {
  flex: 1;
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
}

.pending__count {
  font-size: var(--font-size-base);
  font-weight: 600;
}

.pending__count.is-danger {
  color: var(--color-danger);
}

.pending__count.is-warning {
  color: var(--color-warning);
}

.pending__count.is-info {
  color: var(--color-info-main);
}

.pending__arrow {
  font-size: 12px;
  color: var(--color-text-placeholder);
}
</style>
