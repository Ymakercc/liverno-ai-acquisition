<script setup lang="ts">
import { computed } from 'vue'
import type { DailyGoal } from '@/types/dashboard'

const props = defineProps<{ goal: DailyGoal }>()

/** 进度条宽度，超额完成时封顶 100% */
const progress = computed<number>(() => Math.min(props.goal.rate, 100))
const gap = computed<number>(() => Math.max(props.goal.target - props.goal.current, 0))
</script>

<template>
  <section class="goal-card app-card">
    <div class="goal-card__main">
      <div class="goal-card__head">
        <h2 class="goal-card__title">
          今日有效企业
        </h2>
        <el-tag
          :type="goal.achieved ? 'success' : 'warning'"
          size="small"
          effect="light"
        >
          {{ goal.achieved ? '已达标' : '未达标' }}
        </el-tag>
      </div>

      <div class="goal-card__value">
        <span class="goal-card__current num">{{ goal.current }}</span>
        <span class="goal-card__target num">/ {{ goal.target }}</span>
      </div>

      <div class="goal-card__bar">
        <div
          class="goal-card__bar-inner"
          :class="{ 'is-achieved': goal.achieved }"
          :style="{ width: `${progress}%` }"
        />
      </div>

      <p class="goal-card__hint">
        有效企业 = 去重后 + AI 判断 is_relevant = true，原始抓取数量不计入目标。
      </p>
    </div>

    <div class="goal-card__side">
      <div class="goal-card__stat">
        <span class="goal-card__stat-label">完成率</span>
        <span class="goal-card__stat-value num">{{ goal.rate }}%</span>
      </div>
      <div class="goal-card__stat">
        <span class="goal-card__stat-label">距目标</span>
        <span class="goal-card__stat-value num">{{ gap }}</span>
      </div>
      <div class="goal-card__stat">
        <span class="goal-card__stat-label">统计日期</span>
        <span class="goal-card__stat-value">{{ goal.date }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.goal-card {
  display: flex;
  gap: 32px;
  align-items: stretch;
  padding: var(--space-xl);
}

.goal-card__main {
  flex: 1;
  min-width: 0;
}

.goal-card__head {
  display: flex;
  gap: 10px;
  align-items: center;
}

.goal-card__title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

.goal-card__value {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-top: 12px;
}

.goal-card__current {
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-primary);
}

.goal-card__target {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.goal-card__bar {
  width: 100%;
  height: 8px;
  margin-top: 16px;
  overflow: hidden;
  background: var(--color-border-light);
  border-radius: 4px;
}

.goal-card__bar-inner {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
}

.goal-card__bar-inner.is-achieved {
  background: var(--color-success);
}

.goal-card__hint {
  margin: 12px 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.goal-card__side {
  display: flex;
  flex: 0 0 240px;
  flex-direction: column;
  justify-content: center;
  gap: 14px;
  padding-left: 32px;
  border-left: 1px solid var(--color-border-light);
}

.goal-card__stat {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.goal-card__stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.goal-card__stat-value {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

@media (max-width: 1279px) {
  .goal-card {
    gap: 20px;
  }

  .goal-card__side {
    flex-basis: 200px;
    padding-left: 20px;
  }
}
</style>
