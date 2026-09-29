<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import GoalCard from './components/GoalCard.vue'
import MetricGrid from './components/MetricGrid.vue'
import FunnelFlow from './components/FunnelFlow.vue'
import PendingPanel from './components/PendingPanel.vue'
import ActivityPanel from './components/ActivityPanel.vue'
import { fetchDashboardOverview } from '@/api/dashboard'
import type { DashboardOverview } from '@/types/dashboard'

const router = useRouter()

const overview = ref<DashboardOverview | null>(null)
const loading = ref(true)
const error = ref(false)

/** 离开页面时中止未完成请求 */
let controller: AbortController | null = null

/** 数据源由 VITE_USE_MOCK 决定，页面只依赖 API 层 */
async function loadOverview(): Promise<void> {
  controller?.abort()
  controller = new AbortController()

  loading.value = true
  error.value = false
  try {
    overview.value = await fetchDashboardOverview(controller.signal)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function goTo(path: string): void {
  router.push(path)
}

onMounted(loadOverview)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="dashboard">
    <el-skeleton
      v-if="loading"
      :rows="8"
      animated
    />

    <el-result
      v-else-if="error || !overview"
      icon="warning"
      title="数据加载失败"
      sub-title="请稍后重试"
    >
      <template #extra>
        <el-button
          type="primary"
          @click="loadOverview"
        >
          重新加载
        </el-button>
      </template>
    </el-result>

    <template v-else>
      <GoalCard :goal="overview.goal" />

      <MetricGrid
        :metrics="overview.metrics"
        @navigate="goTo"
      />

      <FunnelFlow
        :nodes="overview.funnel"
        @navigate="goTo"
      />

      <div class="dashboard__split">
        <PendingPanel
          :tasks="overview.pending"
          @navigate="goTo"
        />
        <ActivityPanel :activities="overview.activities" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

/* 第四层：左侧待处理 / 右侧运行动态 */
.dashboard__split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-base);
  /* 左右等高，避免条数不同导致一侧底部留白 */
  align-items: stretch;
}

@media (max-width: 1279px) {
  .dashboard__split {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
