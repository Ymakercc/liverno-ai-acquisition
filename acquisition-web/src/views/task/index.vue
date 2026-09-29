<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TaskFormDrawer from './components/TaskFormDrawer.vue'
import { fetchTaskStats, fetchTasks, runTask } from '@/api/task'
import { CHANNEL_OPTIONS, TASK_STATUS_OPTIONS, labelOf } from '@/mock/dict'
import type { AcquisitionTask, TaskQuery, TaskStatus } from '@/types/task'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  task_name: (route.query.task_name as string) ?? '',
  profile_name: (route.query.profile_name as string) ?? '',
  strategy_id: (route.query.strategy_id_filter as string) ?? '',
  status: (route.query.status as string) ?? ''
})

const page = ref<number>(Number(route.query.page) || 1)
const pageSize = ref<number>(Number(route.query.page_size) || 20)

const list = ref<AcquisitionTask[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)

const stats = reactive({ total: 0, pending: 0, running: 0, completed: 0, failed: 0 })

const formVisible = ref(false)
const formStrategyId = ref<string | null>(null)

let controller: AbortController | null = null
let searchTimer: number | undefined
let pollTimer: number | undefined

function buildQuery(): TaskQuery {
  const query: TaskQuery = { page: page.value, page_size: pageSize.value }
  if (filters.task_name.trim()) query.task_name = filters.task_name.trim()
  if (filters.profile_name.trim()) query.profile_name = filters.profile_name.trim()
  if (filters.strategy_id.trim()) query.strategy_id = filters.strategy_id.trim()
  if (filters.status) query.status = filters.status as TaskStatus
  return query
}

function syncUrl(): void {
  router.replace({
    query: {
      ...(filters.task_name ? { task_name: filters.task_name } : {}),
      ...(filters.profile_name ? { profile_name: filters.profile_name } : {}),
      ...(filters.strategy_id ? { strategy_id_filter: filters.strategy_id } : {}),
      ...(filters.status ? { status: filters.status } : {}),
      page: String(page.value),
      page_size: String(pageSize.value)
    }
  })
}

async function loadList(silent = false): Promise<void> {
  controller?.abort()
  controller = new AbortController()

  if (!silent) loading.value = true
  error.value = false
  try {
    const result = await fetchTasks(buildQuery(), controller.signal)
    list.value = result.list
    total.value = result.total
  } catch {
    if (!silent) {
      error.value = true
      list.value = []
      total.value = 0
    }
  } finally {
    loading.value = false
  }
}

async function loadStats(): Promise<void> {
  try {
    const result = await fetchTaskStats()
    Object.assign(stats, result)
  } catch {
    Object.assign(stats, { total: 0, pending: 0, running: 0, completed: 0, failed: 0 })
  }
}

function refreshAll(silent = false): void {
  loadList(silent)
  loadStats()
}

/* ---------------- 执行中任务轮询：5s，页面不可见时暂停（CLAUDE.md 8.4） ---------------- */

function stopPolling(): void {
  window.clearInterval(pollTimer)
  pollTimer = undefined
}

function startPolling(): void {
  stopPolling()
  pollTimer = window.setInterval(() => {
    if (document.hidden) return
    if (list.value.some((item) => item.status === 'running')) refreshAll(true)
  }, 5000)
}

function handleVisibility(): void {
  if (document.hidden) stopPolling()
  else startPolling()
}

/* ---------------- 筛选 ---------------- */

function handleSearch(): void {
  page.value = 1
  syncUrl()
  loadList()
}

function handleReset(): void {
  filters.task_name = ''
  filters.profile_name = ''
  filters.strategy_id = ''
  filters.status = ''
  handleSearch()
}

watch([() => filters.task_name, () => filters.profile_name, () => filters.strategy_id], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(handleSearch, 400)
})

function handlePageChange(value: number): void {
  page.value = value
  syncUrl()
  loadList()
}

function handleSizeChange(value: number): void {
  pageSize.value = value
  page.value = 1
  syncUrl()
  loadList()
}

/* ---------------- 操作 ---------------- */

function asTask(row: unknown): AcquisitionTask {
  return row as AcquisitionTask
}

function goDetail(task: AcquisitionTask): void {
  router.push(`/acquisition-tasks/${task.id}`)
}

async function handleRun(task: AcquisitionTask): Promise<void> {
  try {
    const result = await runTask(task.id)
    if (result.status === 'failed') ElMessage.error(result.failure_reason || '任务执行失败')
    else ElMessage.success('任务执行完成')
    refreshAll()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '执行失败')
  }
}

function openCreate(strategyId?: string): void {
  formStrategyId.value = strategyId ?? null
  formVisible.value = true
}

function handleCreated(taskId: string): void {
  refreshAll()
  router.push(`/acquisition-tasks/${taskId}`)
}

/** 来自搜索策略页：/acquisition-tasks?strategy_id=xxx&action=create */
function handleEntryQuery(): void {
  const strategyId = route.query.strategy_id as string | undefined
  const action = route.query.action as string | undefined
  if (strategyId && action === 'create') openCreate(strategyId)
}

onMounted(() => {
  refreshAll()
  handleEntryQuery()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(searchTimer)
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<template>
  <div class="task-page">
    <!-- 标题区 -->
    <section class="task-page__intro app-card">
      <div class="task-page__intro-main">
        <h2 class="task-page__title">
          获客任务
        </h2>
        <p class="task-page__desc">
          按搜索策略执行真实企业发现，结果经标准化与全局去重后进入候选企业库。
        </p>
        <div class="task-page__stats">
          <span class="task-page__stat">
            <i class="task-page__stat-dot is-total" />
            任务总数 <b class="num">{{ stats.total }}</b>
          </span>
          <span class="task-page__stat">
            <i class="task-page__stat-dot is-pending" />
            待执行 <b class="num">{{ stats.pending }}</b>
          </span>
          <span class="task-page__stat">
            <i class="task-page__stat-dot is-running" />
            执行中 <b class="num">{{ stats.running }}</b>
          </span>
          <span class="task-page__stat">
            <i class="task-page__stat-dot is-completed" />
            已完成 <b class="num">{{ stats.completed }}</b>
          </span>
          <span class="task-page__stat">
            <i class="task-page__stat-dot is-failed" />
            失败 <b class="num">{{ stats.failed }}</b>
          </span>
        </div>
      </div>
      <el-button
        type="primary"
        @click="openCreate()"
      >
        <el-icon><Plus /></el-icon>
        新建获客任务
      </el-button>
    </section>

    <!-- 筛选 -->
    <section class="task-page__filter app-card">
      <el-input
        v-model="filters.task_name"
        class="task-page__filter-item"
        placeholder="搜索任务名称"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-input
        v-model="filters.profile_name"
        class="task-page__filter-item"
        placeholder="来源画像"
        clearable
      />
      <el-input
        v-model="filters.strategy_id"
        class="task-page__filter-item"
        placeholder="搜索策略编号"
        clearable
      />
      <el-select
        v-model="filters.status"
        class="task-page__filter-item"
        placeholder="状态"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in TASK_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <div class="task-page__filter-actions">
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </section>

    <!-- 列表 -->
    <section class="task-page__table app-card">
      <header class="task-page__table-head">
        <h3 class="task-page__table-title">
          任务列表
        </h3>
        <span class="task-page__table-count">共 <b class="num">{{ total }}</b> 条</span>
      </header>

      <el-result
        v-if="error"
        icon="warning"
        title="数据加载失败"
        sub-title="请检查网络后重试"
      >
        <template #extra>
          <el-button
            type="primary"
            @click="loadList()"
          >
            重新加载
          </el-button>
        </template>
      </el-result>

      <template v-else>
        <el-table
          v-loading="loading"
          :data="list"
          row-key="id"
          stripe
          class="task-table"
        >
          <template #empty>
            <el-empty
              :image-size="80"
              description="暂无获客任务，可从搜索策略页点击「创建获客任务」"
            />
          </template>

          <el-table-column
            label="任务名称"
            min-width="230"
            fixed="left"
          >
            <template #default="{ row }">
              <div class="task-cell">
                <div class="task-cell__name">
                  {{ asTask(row).task_name }}
                </div>
                <div class="task-cell__meta">
                  <span class="num">{{ asTask(row).id }}</span>
                  <span class="task-cell__divider">·</span>
                  <span>{{ asTask(row).profile_name }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="搜索策略"
            width="150"
          >
            <template #default="{ row }">
              <span class="num">{{ asTask(row).strategy_code }}</span>
              <span class="task-cell__version num"> · v{{ asTask(row).strategy_version }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="渠道"
            min-width="170"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="asTask(row).channel_snapshots.map((item) => labelOf(CHANNEL_OPTIONS, item.channel)).join('、')"
                placement="top"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in asTask(row).channel_snapshots.slice(0, 2)"
                    :key="item.channel"
                    class="tag-cell__item"
                  >{{ labelOf(CHANNEL_OPTIONS, item.channel) }}</span>
                  <span
                    v-if="asTask(row).channel_snapshots.length > 2"
                    class="tag-cell__more"
                  >+{{ asTask(row).channel_snapshots.length - 2 }}</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="状态"
            width="100"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="chip"
                :class="`is-${asTask(row).status}`"
              >
                {{ labelOf(TASK_STATUS_OPTIONS, asTask(row).status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="搜索结果"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              <span class="num result-num is-raw">{{ asTask(row).search_results_count }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="有效域名"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              <span class="num result-num">{{ asTask(row).valid_domains_count }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="新增企业"
            width="110"
            align="right"
          >
            <template #default="{ row }">
              <span class="num result-num is-relevant">{{ asTask(row).new_enterprises_count }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="开始时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asTask(row).started_at || '-' }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asTask(row).updated_at }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="操作"
            width="190"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-if="asTask(row).status === 'pending'"
                  size="small"
                  type="primary"
                  plain
                  @click="handleRun(asTask(row))"
                >
                  启动任务
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  plain
                  @click="goDetail(asTask(row))"
                >
                  查看结果
                </el-button>

                <el-button
                  link
                  class="row-actions__link"
                  @click="goDetail(asTask(row))"
                >
                  查看任务
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="task-page__pagination">
          <el-pagination
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </template>
    </section>

    <TaskFormDrawer
      v-model="formVisible"
      :strategy-id="formStrategyId"
      @created="handleCreated"
    />
  </div>
</template>

<style scoped>
.task-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

.task-page__intro {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 20px var(--space-xl);
}

.task-page__intro-main {
  min-width: 0;
}

.task-page__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: 28px;
  color: var(--color-text-primary);
}

.task-page__desc {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.task-page__stats {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-top: 12px;
}

.task-page__stat {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.task-page__stat b {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-page__stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.task-page__stat-dot.is-total {
  background: var(--color-primary);
}

.task-page__stat-dot.is-pending {
  background: var(--color-text-placeholder);
}

.task-page__stat-dot.is-running {
  background: var(--color-info-main);
}

.task-page__stat-dot.is-completed {
  background: var(--color-success);
}

.task-page__stat-dot.is-failed {
  background: var(--color-danger);
}

.task-page__filter {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 14px var(--space-xl);
}

.task-page__filter-item {
  width: 190px;
}

.task-page__filter-actions {
  margin-left: auto;
}

.task-page__table {
  padding: 0 0 var(--space-xl);
}

.task-page__table-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 16px var(--space-xl) 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.task-page__table-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-page__table-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.task-page__table-count b {
  color: var(--color-text-primary);
}

.task-table {
  padding: 0 var(--space-xl);
}

.task-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px var(--space-xl) 0;
}

.task-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.task-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

.task-table :deep(.el-table .cell) {
  white-space: nowrap;
}

.task-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-primary-bg);
}

.task-cell__name {
  overflow: hidden;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-cell__meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.task-cell__divider {
  color: var(--color-border);
}

.task-cell__version {
  color: var(--color-text-secondary);
}

.tag-cell {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
  overflow: hidden;
}

.tag-cell__item {
  flex: 0 0 auto;
  padding: 1px 8px;
  font-size: var(--font-size-xs);
  line-height: 20px;
  color: var(--color-text-primary);
  white-space: nowrap;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.tag-cell__more {
  flex: 0 0 auto;
  padding: 1px 6px;
  font-size: var(--font-size-xs);
  line-height: 20px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
}

/* 三个结果数字：AI 有效是目标考核口径，视觉最重 */
.result-num {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.result-num.is-raw {
  color: var(--color-text-primary);
}

.result-num.is-relevant {
  font-size: var(--font-size-md);
  font-weight: 700;
  color: var(--color-primary);
}

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

.muted-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  white-space: nowrap;
}

.row-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  align-items: center;
  white-space: nowrap;
}

.row-actions__link {
  flex: 0 0 auto;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.row-actions__link:hover {
  color: var(--color-primary);
}
</style>
