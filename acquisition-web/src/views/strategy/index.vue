<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StrategyFormDrawer from './components/StrategyFormDrawer.vue'
import StrategyDetailDrawer from './components/StrategyDetailDrawer.vue'
import {
  fetchStrategies,
  fetchStrategy,
  fetchStrategyStats,
  updateStrategyStatus
} from '@/api/strategy'
import {
  CHANNEL_OPTIONS,
  COUNTRY_OPTIONS,
  STRATEGY_STATUS_OPTIONS,
  labelOf,
  labelsOf
} from '@/mock/dict'
import type { Option } from '@/types/common'
import type { SearchStrategy, StrategyQuery, StrategyStatus } from '@/types/strategy'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  profile_name: (route.query.profile_name as string) ?? '',
  channel: (route.query.channel as string) ?? '',
  status: (route.query.status as string) ?? ''
})

const page = ref<number>(Number(route.query.page) || 1)
const pageSize = ref<number>(Number(route.query.page_size) || 20)

const list = ref<SearchStrategy[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)

/** 顶部轻量统计：复用列表接口的 total 字段，不新增接口语义 */
const stats = reactive({ total: 0, active: 0, draft: 0, paused: 0 })

const formVisible = ref(false)
const formMode = ref<'generate' | 'edit' | 'regenerate'>('generate')
const formProfileId = ref<string | null>(null)
const formStrategyId = ref<string | null>(null)

const detailVisible = ref(false)
const currentStrategy = ref<SearchStrategy | null>(null)

let controller: AbortController | null = null
let searchTimer: number | undefined

function buildQuery(): StrategyQuery {
  const query: StrategyQuery = { page: page.value, page_size: pageSize.value }
  if (filters.profile_name.trim()) query.profile_name = filters.profile_name.trim()
  if (filters.channel) query.channel = filters.channel
  if (filters.status) query.status = filters.status as StrategyStatus
  return query
}

function syncUrl(): void {
  router.replace({
    query: {
      ...(filters.profile_name ? { profile_name: filters.profile_name } : {}),
      ...(filters.channel ? { channel: filters.channel } : {}),
      ...(filters.status ? { status: filters.status } : {}),
      page: String(page.value),
      page_size: String(pageSize.value)
    }
  })
}

async function loadList(): Promise<void> {
  controller?.abort()
  controller = new AbortController()

  loading.value = true
  error.value = false
  try {
    const result = await fetchStrategies(buildQuery(), controller.signal)
    list.value = result.list
    total.value = result.total
  } catch {
    error.value = true
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/**
 * 顶部统计
 * 优先调用 stats 接口；后端尚未提供时降级为列表接口计数，
 * 两者都失败也只是统计归零，不影响列表与主流程。
 */
async function loadStats(): Promise<void> {
  try {
    const result = await fetchStrategyStats()
    stats.total = result.total
    stats.active = result.active
    stats.draft = result.draft
    stats.paused = result.paused
    return
  } catch {
    // 继续走降级方案
  }

  try {
    const [all, active, draft, paused] = await Promise.all([
      fetchStrategies({ page: 1, page_size: 1 }),
      fetchStrategies({ page: 1, page_size: 1, status: 'active' }),
      fetchStrategies({ page: 1, page_size: 1, status: 'draft' }),
      fetchStrategies({ page: 1, page_size: 1, status: 'paused' })
    ])
    stats.total = all.total
    stats.active = active.total
    stats.draft = draft.total
    stats.paused = paused.total
  } catch {
    stats.total = 0
    stats.active = 0
    stats.draft = 0
    stats.paused = 0
  }
}

function refreshAll(): void {
  loadList()
  loadStats()
}

function handleSearch(): void {
  page.value = 1
  syncUrl()
  loadList()
}

function handleReset(): void {
  filters.profile_name = ''
  filters.channel = ''
  filters.status = ''
  handleSearch()
}

watch(
  () => filters.profile_name,
  () => {
    window.clearTimeout(searchTimer)
    searchTimer = window.setTimeout(handleSearch, 400)
  }
)

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

/** el-table 插槽 row 为 DefaultRow，统一在此收窄 */
function asStrategy(row: unknown): SearchStrategy {
  return row as SearchStrategy
}

function channelLabels(strategy: SearchStrategy): string[] {
  return strategy.channel_strategies.map((item) => labelOf(CHANNEL_OPTIONS, item.channel))
}

function visibleChannels(strategy: SearchStrategy): string[] {
  return channelLabels(strategy).slice(0, 2)
}

function restChannels(strategy: SearchStrategy): number {
  return Math.max(strategy.channel_strategies.length - 2, 0)
}

function queryCount(strategy: SearchStrategy): number {
  return strategy.channel_strategies.reduce((sum, item) => sum + item.queries.length, 0)
}

/** 策略覆盖的国家：各渠道去重合并 */
function countryCodes(strategy: SearchStrategy): string[] {
  const set = new Set<string>()
  strategy.channel_strategies.forEach((channel) => {
    channel.target_countries.forEach((code) => set.add(code))
  })
  return Array.from(set)
}

function visibleCountries(strategy: SearchStrategy): string[] {
  return labelsOf(COUNTRY_OPTIONS, countryCodes(strategy)).slice(0, 2)
}

function restCountries(strategy: SearchStrategy): number {
  return Math.max(countryCodes(strategy).length - 2, 0)
}

function allLabels(options: Option[], values: string[]): string {
  return labelsOf(options, values).join('、') || '-'
}

/* ---------------- 操作 ---------------- */

/**
 * 从客户画像进入生成
 * 一个画像只维护一套策略：已存在时先提示，确认后走重新生成（version + 1），
 * 不静默覆盖、也不产生第二条并行策略。
 */
async function openGenerate(profileId: string): Promise<void> {
  let existing: SearchStrategy | undefined
  try {
    const result = await fetchStrategies({ page: 1, page_size: 1, profile_id: profileId })
    existing = result.list[0]
  } catch {
    existing = undefined
  }

  if (existing) {
    try {
      await ElMessageBox.confirm(
        '重新生成将基于当前画像生成新的策略版本，已有获客任务不会受到影响。是否继续？',
        '该客户画像已经存在搜索策略',
        { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
    formMode.value = 'regenerate'
    formProfileId.value = null
    formStrategyId.value = existing.id
    formVisible.value = true
    return
  }

  formMode.value = 'generate'
  formProfileId.value = profileId
  formStrategyId.value = null
  formVisible.value = true
}

function openEdit(row: SearchStrategy): void {
  formMode.value = 'edit'
  formProfileId.value = null
  formStrategyId.value = row.id
  formVisible.value = true
}

async function openRegenerate(row: SearchStrategy): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将基于画像「${row.profile_name}」重新生成搜索策略（v${row.version} → v${row.version + 1}）。生成结果需人工确认后保存才会生效，保存前原策略继续有效；已创建的获客任务不受影响。`,
      '重新生成策略',
      { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  formMode.value = 'regenerate'
  formProfileId.value = null
  formStrategyId.value = row.id
  formVisible.value = true
}

async function openDetail(row: SearchStrategy): Promise<void> {
  try {
    currentStrategy.value = await fetchStrategy(row.id)
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载失败')
  }
}

/** 上游画像已暂停：策略 status 不变，但不可产生新获客任务 */
function isBlockedByProfile(strategy: SearchStrategy): boolean {
  return strategy.profile_enabled === false
}

/** 满足创建获客任务的全部条件：画像启用 + 策略 active + 有效渠道与 Query */
function canCreateTask(strategy: SearchStrategy): boolean {
  return strategy.status === 'active' && !isBlockedByProfile(strategy)
}

function taskBlockedReason(strategy: SearchStrategy): string {
  if (isBlockedByProfile(strategy)) return '上游客户画像已暂停，暂不能创建新的获客任务'
  return '仅启用状态的策略可创建获客任务'
}

async function toggleStatus(row: SearchStrategy): Promise<void> {
  const nextStatus: StrategyStatus = row.status === 'active' ? 'paused' : 'active'
  const action = nextStatus === 'active' ? '启用' : '暂停'
  try {
    await ElMessageBox.confirm(
      nextStatus === 'active'
        ? `确定启用画像「${row.profile_name}」的搜索策略吗？启用后可用于创建新的获客任务。`
        : `确定暂停该策略吗？暂停后不再产生新的自动获客任务，已创建与执行中的任务不受影响。`,
      `${action}策略`,
      {
        confirmButtonText: action,
        cancelButtonText: '取消',
        type: nextStatus === 'active' ? 'info' : 'warning'
      }
    )
  } catch {
    return
  }

  try {
    const updated = await updateStrategyStatus(row.id, { status: nextStatus })
    Object.assign(row, updated)
    ElMessage.success(`已${action}`)
    refreshAll()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败')
  }
}

/** 下一步业务动作：创建获客任务（获客任务模块尚未开发，此处仅跳转预留） */
function goCreateTask(row: SearchStrategy): void {
  router.push({
    path: '/acquisition-tasks',
    query: { strategy_id: row.id, action: 'create' }
  })
}

function handleCommand(command: string, row: SearchStrategy): void {
  if (command === 'edit') openEdit(row)
  if (command === 'regenerate') openRegenerate(row)
  if (command === 'status') toggleStatus(row)
}

function handleSaved(): void {
  refreshAll()
}

/** 来自客户画像页的跳转：/search-strategies?profile_id=xxx&action=generate */
function handleEntryQuery(): void {
  const profileId = route.query.profile_id as string | undefined
  const action = route.query.action as string | undefined
  if (profileId && action === 'generate') {
    openGenerate(profileId)
  }
}

onMounted(() => {
  refreshAll()
  handleEntryQuery()
})

onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="strategy-page">
    <!-- 标题区 -->
    <section class="strategy-page__intro app-card">
      <div class="strategy-page__intro-main">
        <h2 class="strategy-page__title">
          搜索策略
        </h2>
        <p class="strategy-page__desc">
          AI 根据客户画像生成多渠道搜索方案，用于指导企业发现任务。
        </p>
        <div class="strategy-page__stats">
          <span class="strategy-page__stat">
            <i class="strategy-page__stat-dot is-total" />
            策略总数
            <b class="num">{{ stats.total }}</b>
          </span>
          <span class="strategy-page__stat">
            <i class="strategy-page__stat-dot is-active" />
            启用中
            <b class="num">{{ stats.active }}</b>
          </span>
          <span class="strategy-page__stat">
            <i class="strategy-page__stat-dot is-draft" />
            草稿
            <b class="num">{{ stats.draft }}</b>
          </span>
          <span class="strategy-page__stat">
            <i class="strategy-page__stat-dot is-paused" />
            已暂停
            <b class="num">{{ stats.paused }}</b>
          </span>
        </div>
      </div>
      <el-button @click="router.push('/profiles')">
        <el-icon><Plus /></el-icon>
        从客户画像生成
      </el-button>
    </section>

    <!-- 筛选工具条 -->
    <section class="strategy-page__filter app-card">
      <el-input
        v-model="filters.profile_name"
        class="strategy-page__filter-item"
        placeholder="搜索来源画像"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="filters.channel"
        class="strategy-page__filter-item"
        placeholder="渠道"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in CHANNEL_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.status"
        class="strategy-page__filter-item"
        placeholder="状态"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in STRATEGY_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <div class="strategy-page__filter-actions">
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </section>

    <!-- 列表模块 -->
    <section class="strategy-page__table app-card">
      <header class="strategy-page__table-head">
        <h3 class="strategy-page__table-title">
          策略列表
        </h3>
        <span class="strategy-page__table-count">共 <b class="num">{{ total }}</b> 条</span>
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
            @click="loadList"
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
          class="strategy-table"
        >
          <template #empty>
            <el-empty
              :image-size="80"
              description="暂无搜索策略，请先到客户画像页点击「生成搜索策略」"
            />
          </template>

          <el-table-column
            label="来源画像"
            min-width="240"
            fixed="left"
          >
            <template #default="{ row }">
              <div class="strategy-cell">
                <div class="strategy-cell__name">
                  {{ asStrategy(row).profile_name }}
                </div>
                <div class="strategy-cell__meta">
                  <span class="num">{{ asStrategy(row).id }}</span>
                  <span class="strategy-cell__divider">·</span>
                  <span class="num">v{{ asStrategy(row).version }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="覆盖渠道"
            min-width="200"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="channelLabels(asStrategy(row)).join('、')"
                placement="top"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleChannels(asStrategy(row))"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restChannels(asStrategy(row))"
                    class="tag-cell__more"
                  >+{{ restChannels(asStrategy(row)) }}</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="搜索 Query"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              <span class="quota">
                <b class="quota__value num">{{ queryCount(asStrategy(row)) }}</b>
                <span class="quota__unit">条</span>
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="目标国家"
            min-width="170"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="allLabels(COUNTRY_OPTIONS, countryCodes(asStrategy(row)))"
                placement="top"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleCountries(asStrategy(row))"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restCountries(asStrategy(row))"
                    class="tag-cell__more"
                  >+{{ restCountries(asStrategy(row)) }}</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="版本"
            width="86"
            align="center"
          >
            <template #default="{ row }">
              <span class="version-chip num">v{{ asStrategy(row).version }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="状态"
            width="150"
            align="center"
          >
            <template #default="{ row }">
              <div class="status-cell">
                <span
                  class="chip"
                  :class="`is-${asStrategy(row).status}`"
                >
                  {{ labelOf(STRATEGY_STATUS_OPTIONS, asStrategy(row).status) }}
                </span>
                <el-tooltip
                  v-if="isBlockedByProfile(asStrategy(row))"
                  content="上游客户画像已暂停，该策略不会产生新的获客任务；策略本身状态未被修改"
                  placement="top"
                >
                  <span class="chip is-blocked">画像已暂停</span>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asStrategy(row).updated_at }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="操作"
            width="230"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="row-actions">
                <el-tooltip
                  :disabled="canCreateTask(asStrategy(row))"
                  :content="taskBlockedReason(asStrategy(row))"
                  placement="top"
                >
                  <span>
                    <el-button
                      size="small"
                      type="primary"
                      plain
                      :disabled="!canCreateTask(asStrategy(row))"
                      @click="goCreateTask(asStrategy(row))"
                    >
                      创建获客任务
                    </el-button>
                  </span>
                </el-tooltip>
                <el-button
                  link
                  class="row-actions__link"
                  @click="openDetail(asStrategy(row))"
                >
                  查看
                </el-button>
                <el-dropdown
                  :key="`${asStrategy(row).id}-${asStrategy(row).status}`"
                  trigger="click"
                  @command="(command: string) => handleCommand(command, asStrategy(row))"
                >
                  <span class="row-actions__more">
                    更多
                    <el-icon><ArrowDown /></el-icon>
                  </span>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">
                        编辑
                      </el-dropdown-item>
                      <el-dropdown-item command="regenerate">
                        重新生成
                      </el-dropdown-item>
                      <el-dropdown-item command="status">
                        {{ asStrategy(row).status === 'active' ? '暂停' : '启用' }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="strategy-page__pagination">
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

    <StrategyFormDrawer
      v-model="formVisible"
      :mode="formMode"
      :profile-id="formProfileId"
      :strategy-id="formStrategyId"
      @saved="handleSaved"
    />
    <StrategyDetailDrawer
      v-model="detailVisible"
      :strategy="currentStrategy"
    />
  </div>
</template>

<style scoped>
.strategy-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

/* ---------- 标题区 ---------- */
.strategy-page__intro {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 20px var(--space-xl);
}

.strategy-page__intro-main {
  min-width: 0;
}

.strategy-page__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: 28px;
  color: var(--color-text-primary);
}

.strategy-page__desc {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.strategy-page__stats {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-top: 12px;
}

.strategy-page__stat {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.strategy-page__stat b {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.strategy-page__stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.strategy-page__stat-dot.is-total {
  background: var(--color-primary);
}

.strategy-page__stat-dot.is-active {
  background: var(--color-success);
}

.strategy-page__stat-dot.is-draft {
  background: var(--color-info-main);
}

.strategy-page__stat-dot.is-paused {
  background: var(--color-text-placeholder);
}

/* ---------- 筛选 ---------- */
.strategy-page__filter {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 14px var(--space-xl);
}

.strategy-page__filter-item {
  width: 200px;
}

.strategy-page__filter-actions {
  margin-left: auto;
}

/* ---------- 列表模块 ---------- */
.strategy-page__table {
  padding: 0 0 var(--space-xl);
}

.strategy-page__table-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 16px var(--space-xl) 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.strategy-page__table-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.strategy-page__table-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.strategy-page__table-count b {
  color: var(--color-text-primary);
}

.strategy-table {
  padding: 0 var(--space-xl);
}

.strategy-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px var(--space-xl) 0;
}

.strategy-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.strategy-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

.strategy-table :deep(.el-table .cell) {
  white-space: nowrap;
}

.strategy-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-primary-bg);
}

/* ---------- 主信息列 ---------- */
.strategy-cell__name {
  overflow: hidden;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-cell__meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.strategy-cell__divider {
  color: var(--color-border);
}

/* ---------- 多值列 ---------- */
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

/* ---------- 数值 ---------- */
.quota {
  display: inline-flex;
  gap: 3px;
  align-items: baseline;
}

.quota__value {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

.quota__unit {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.version-chip {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
}

/* ---------- 状态标签 ---------- */
.chip {
  display: inline-block;
  min-width: 40px;
  padding: 0 8px;
  font-size: var(--font-size-xs);
  line-height: 22px;
  text-align: center;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.chip.is-active {
  color: var(--color-success);
  background: #eaf7f2;
  border-color: #c6e9dc;
}

.chip.is-draft {
  color: var(--color-info-text);
  background: var(--color-info-bg);
  border-color: var(--color-info-border);
}

.status-cell {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
}

/* 受上游画像暂停影响：与「人工暂停策略」在视觉上区分开 */
.chip.is-blocked {
  color: var(--color-warning);
  background: #fef6e7;
  border-color: #f7dfb0;
}

.chip.is-paused {
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border-color: var(--color-border);
}

.muted-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  white-space: nowrap;
}

/* ---------- 操作列 ---------- */
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

.row-actions__more {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 2px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
  cursor: pointer;
}

.row-actions__more:hover {
  color: var(--color-primary);
}
</style>
