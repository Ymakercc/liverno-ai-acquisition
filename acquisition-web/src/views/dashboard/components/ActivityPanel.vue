<script setup lang="ts">
import type { ActivityItem } from '@/types/dashboard'

defineProps<{ activities: ActivityItem[] }>()
</script>

<template>
  <section class="activity app-card">
    <header class="activity__head">
      <h3 class="activity__title">
        最近运行动态
      </h3>
      <RouterLink
        class="activity__more"
        to="/logs"
      >
        查看运行日志
      </RouterLink>
    </header>

    <ul
      v-if="activities.length"
      class="activity__list"
    >
      <li
        v-for="item in activities"
        :key="item.id"
        class="activity__item"
      >
        <span class="activity__time num">{{ item.time }}</span>
        <span
          class="activity__dot"
          :class="`is-${item.status}`"
        />
        <span class="activity__text">{{ item.title }}</span>
      </li>
    </ul>

    <el-empty
      v-else
      description="暂无运行动态"
      :image-size="72"
    />
  </section>
</template>

<style scoped>
.activity {
  display: flex;
  flex-direction: column;
  padding: var(--space-xl);
}

.activity__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.activity__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.activity__more {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
}

.activity__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: space-between;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.activity__item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 40px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.activity__item:last-child {
  border-bottom: none;
}

.activity__time {
  flex: 0 0 40px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.activity__dot {
  flex: 0 0 6px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.activity__dot.is-success {
  background: var(--color-success);
}

.activity__dot.is-warning {
  background: var(--color-warning);
}

.activity__dot.is-danger {
  background: var(--color-danger);
}

.activity__dot.is-info {
  background: var(--color-info-main);
}

/* AI 产出（AI 分析、AI 意向分类）用 AI 紫 */
.activity__dot.is-ai {
  background: var(--color-ai);
}

.activity__text {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}
</style>
