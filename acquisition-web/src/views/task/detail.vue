<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchTask, pauseTask, retryTask, startTask } from '@/api/task'
import { CHANNEL_OPTIONS, COUNTRY_OPTIONS, TASK_STATUS_OPTIONS, labelOf, labelsOf } from '@/mock/dict'
import type { AcquisitionTask } from '@/types/task'

const route = useRoute()
const router = useRouter()

const taskId = route.params.id as string

const task = ref<AcquisitionTask | null>(null)
const loading = ref(true)
const error = ref(false)
const acting = ref(false)

let controller: AbortController | null = null
let pollTimer: number | undefined

async function loadTask(silent = false): Promise<void> {
  controller?.abort()
  controller = new AbortController()

  if (!silent) loading.value = true
  error.value = false
  try {
    task.value = await fetchTask(taskId, controller.signal)
  } catch {
    if (!silent) {
      error.value = true
      task.value = null
    }
  } finally {
    loading.value = false
  }
}

/** 执行中轮询 5s，页面不可见时暂停（CLAUDE.md 8.4） */
function stopPolling(): void {
  window.clearInterval(pollTimer)
  pollTimer = undefined
}

function startPolling(): void {
  stopPolling()
  pollTimer = window.setInterval(() => {
    if (document.hidden) return
    if (task.value?.status === 'running') loadTask(true)
  }, 5000)
}

function handleVisibility(): void {
  if (document.hidden) stopPolling()
  else startPolling()
}

const statusLabel = computed<string>(() =>
  task.value ? labelOf(TASK_STATUS_OPTIONS, task.value.status) : ''
)

/** 去重率与有效率：帮助判断这次获客跑得怎么样 */
const dedupeRate = computed<string>(() => {
  if (!task.value?.raw_discovered_count) return '-'
  return `${((task.value.deduplicated_count / task.value.raw_discovered_count) * 100).toFixed(1)}%`
})

const relevantRate = computed<string>(() => {
  if (!task.value?.raw_discovered_count) return '-'
  return `${((task.value.relevant_count / task.value.raw_discovered_count) * 100).toFixed(1)}%`
})

async function handleStart(): Promise<void> {
  if (!task.value) return
  acting.value = true
  try {
    await startTask(task.value.id)
    ElMessage.success('任务已启动')
    loadTask()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '启动失败')
  } finally {
    acting.value = false
  }
}

async function handleRetry(): Promise<void> {
  if (!task.value) return
  acting.value = true
  try {
    await retryTask(task.value.id)
    ElMessage.success('任务已重新执行')
    loadTask()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重试失败')
  } finally {
    acting.value = false
  }
}

async function handlePause(): Promise<void> {
  if (!task.value) return
  try {
    await ElMessageBox.confirm(
      `确定暂停任务「${task.value.task_name}」吗？已发现的企业结果会保留。`,
      '暂停任务',
      { confirmButtonText: '暂停', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  acting.value = true
  try {
    await pauseTask(task.value.id)
    ElMessage.success('任务已暂停')
    loadTask()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '暂停失败')
  } finally {
    acting.value = false
  }
}

/** 结果入口：候选企业库按任务筛选（候选企业模块尚未开发，此处仅参数联动） */
function goCompanies(): void {
  if (!task.value) return
  router.push({ path: '/companies', query: { task_id: task.value.id } })
}

function goStrategy(): void {
  if (!task.value) return
  router.push({ path: '/search-strategies', query: { profile_name: task.value.profile_name } })
}

onMounted(() => {
  loadTask()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  controller?.abort()
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<template>
  <div class="task-detail">
    <el-skeleton
      v-if="loading"
      :rows="10"
      animated
    />

    <el-result
      v-else-if="error || !task"
      icon="warning"
      title="任务加载失败"
      sub-title="请检查网络后重试"
    >
      <template #extra>
        <el-button
          type="primary"
          @click="loadTask()"
        >
          重新加载
        </el-button>
      </template>
    </el-result>

    <template v-else>
      <!-- 基本信息 -->
      <section class="task-detail__head app-card">
        <div class="task-detail__head-main">
          <div class="task-detail__title-row">
            <h2 class="task-detail__title">
              {{ task.task_name }}
            </h2>
            <span
              class="chip"
              :class="`is-${task.status}`"
            >{{ statusLabel }}</span>
          </div>
          <div class="task-detail__meta">
            <span class="num">{{ task.id }}</span>
            <span class="task-detail__divider">·</span>
            <span>{{ task.profile_name }}</span>
            <span class="task-detail__divider">·</span>
            <span class="num">{{ task.strategy_id }} v{{ task.strategy_version }}</span>
          </div>
        </div>

        <div class="task-detail__actions">
          <el-button
            v-if="task.status === 'pending' || task.status === 'paused'"
            type="primary"
            :loading="acting"
            @click="handleStart"
          >
            启动任务
          </el-button>
          <el-button
            v-else-if="task.status === 'failed'"
            type="primary"
            :loading="acting"
            @click="handleRetry"
          >
            重试
          </el-button>
          <el-button
            v-else-if="task.status === 'running'"
            :loading="acting"
            @click="handlePause"
          >
            暂停
          </el-button>
          <el-button
            type="primary"
            plain
            :disabled="!task.relevant_count"
            @click="goCompanies"
          >
            查看候选企业
          </el-button>
        </div>
      </section>

      <!-- 失败原因 -->
      <el-alert
        v-if="task.status === 'failed' && task.failure_reason"
        class="task-detail__alert"
        type="error"
        :closable="false"
        show-icon
        title="任务执行失败"
        :description="task.failure_reason"
      />

      <!-- 执行概况 -->
      <section class="task-detail__result app-card">
        <header class="task-detail__section-head">
          <h3 class="task-detail__section-title">
            执行概况
          </h3>
          <span
            v-if="task.status === 'running'"
            class="task-detail__live"
          >执行中，数据每 5 秒刷新</span>
        </header>

        <div class="result-grid">
          <div class="result-card">
            <div class="result-card__label">
              原始发现企业
            </div>
            <div class="result-card__value num">
              {{ task.raw_discovered_count }}
            </div>
            <div class="result-card__hint">
              各渠道原始发现，未去重，不计入 300 目标
            </div>
          </div>
          <div class="result-card">
            <div class="result-card__label">
              去重后企业
            </div>
            <div class="result-card__value num">
              {{ task.deduplicated_count }}
            </div>
            <div class="result-card__hint">
              去重率 {{ dedupeRate }}
            </div>
          </div>
          <div class="result-card is-primary">
            <div class="result-card__label">
              AI 有效企业
              <span class="result-card__ai">AI</span>
            </div>
            <div class="result-card__value num">
              {{ task.relevant_count }}
            </div>
            <div class="result-card__hint">
              is_relevant = true，有效率 {{ relevantRate }}
            </div>
          </div>
        </div>
      </section>

      <div class="task-detail__split">
        <!-- 执行渠道 -->
        <section class="task-detail__channels app-card">
          <header class="task-detail__section-head">
            <h3 class="task-detail__section-title">
              执行渠道
            </h3>
            <span class="task-detail__section-sub">
              共 {{ task.channel_snapshots.length }} 个渠道 · {{ task.query_count }} 条 Query（创建时快照）
            </span>
          </header>

          <div
            v-for="channel in task.channel_snapshots"
            :key="channel.channel"
            class="channel-block"
          >
            <div class="channel-block__head">
              <span class="channel-block__name">{{ labelOf(CHANNEL_OPTIONS, channel.channel) }}</span>
              <span class="channel-block__countries">
                {{ labelsOf(COUNTRY_OPTIONS, channel.target_countries).join('、') }}
              </span>
              <span class="channel-block__count num">发现 {{ channel.raw_discovered_count }}</span>
            </div>
            <ul class="channel-block__queries">
              <li
                v-for="query in channel.queries"
                :key="query"
              >
                {{ query }}
              </li>
            </ul>
          </div>
        </section>

        <!-- 执行状态 -->
        <section class="task-detail__timeline app-card">
          <header class="task-detail__section-head">
            <h3 class="task-detail__section-title">
              执行状态
            </h3>
          </header>

          <el-descriptions
            :column="1"
            border
          >
            <el-descriptions-item label="当前状态">
              {{ statusLabel }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ task.created_at }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ task.started_at || '未开始' }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ task.finished_at || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="最近更新">
              {{ task.updated_at }}
            </el-descriptions-item>
            <el-descriptions-item label="目标国家">
              {{ labelsOf(COUNTRY_OPTIONS, task.target_countries).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="失败原因">
              {{ task.failure_reason || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-button
            link
            type="primary"
            class="task-detail__link"
            @click="goStrategy"
          >
            查看来源搜索策略
          </el-button>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.task-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

/* ---------- 头部 ---------- */
.task-detail__head {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 20px var(--space-xl);
}

.task-detail__title-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.task-detail__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-detail__meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.task-detail__divider {
  color: var(--color-border);
}

.task-detail__actions {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
}

.task-detail__alert {
  border-radius: var(--radius-card);
}

/* ---------- 区块 ---------- */
.task-detail__result,
.task-detail__channels,
.task-detail__timeline {
  padding: 18px var(--space-xl) var(--space-xl);
}

.task-detail__section-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin-bottom: 14px;
}

.task-detail__section-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-detail__section-sub,
.task-detail__live {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.task-detail__live {
  color: var(--color-info-main);
}

/* ---------- 结果卡 ---------- */
.result-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-base);
}

.result-card {
  padding: 16px 18px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.result-card.is-primary {
  background: var(--color-primary-bg);
  border-color: #cddcd9;
}

.result-card__label {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.result-card__ai {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

.result-card__value {
  margin-top: 8px;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-text-primary);
}

.result-card.is-primary .result-card__value {
  color: var(--color-primary);
}

.result-card__hint {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

/* ---------- 下半区 ---------- */
.task-detail__split {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--space-base);
  align-items: stretch;
}

@media (max-width: 1279px) {
  .task-detail__split {
    grid-template-columns: minmax(0, 1fr);
  }

  .result-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* ---------- 渠道块 ---------- */
.channel-block {
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.channel-block:last-child {
  margin-bottom: 0;
}

.channel-block__head {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.channel-block__name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.channel-block__countries {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.channel-block__count {
  margin-left: auto;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.channel-block__queries {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  word-break: break-all;
}

.channel-block__queries li {
  margin-bottom: 4px;
}

.task-detail__link {
  margin-top: 12px;
}

/* ---------- 状态标签 ---------- */
.chip {
  display: inline-block;
  min-width: 44px;
  padding: 0 8px;
  font-size: var(--font-size-xs);
  line-height: 22px;
  text-align: center;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.chip.is-pending {
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border-color: var(--color-border);
}

.chip.is-running {
  color: var(--color-info-text);
  background: var(--color-info-bg);
  border-color: var(--color-info-border);
}

.chip.is-completed {
  color: var(--color-success);
  background: #eaf7f2;
  border-color: #c6e9dc;
}

.chip.is-failed {
  color: var(--color-danger);
  background: #fdeced;
  border-color: #f7c9cb;
}

.chip.is-paused {
  color: var(--color-warning);
  background: #fef6e7;
  border-color: #f7dfb0;
}
</style>
