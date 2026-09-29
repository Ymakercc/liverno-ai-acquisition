<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchCompanies, fetchCompanyStats } from '@/api/company'
import { fetchProfiles } from '@/api/profile'
import { fetchTask } from '@/api/task'
import {
  CHANNEL_OPTIONS,
  COUNTRY_OPTIONS,
  GRADE_OPTIONS,
  INDUSTRY_OPTIONS,
  RELEVANCE_OPTIONS,
  labelOf
} from '@/mock/dict'
import type { CompanyGrade, CompanyQuery, Enterprise, RelevanceFilter } from '@/types/company'
import type { CustomerProfile } from '@/types/profile'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  company_name: (route.query.company_name as string) ?? '',
  country: (route.query.country as string) ?? '',
  industry: (route.query.industry as string) ?? '',
  channel: (route.query.channel as string) ?? '',
  relevance: (route.query.relevance as string) ?? '',
  grade: (route.query.grade as string) ?? '',
  task_id: (route.query.task_id as string) ?? '',
  /**
   * 画像语境：相关性是「企业 × 画像」的判断，列表必须明确基于哪个画像。
   * 带 task_id 进入时由任务推导并锁定；否则由用户显式选择。
   */
  profile_id: (route.query.profile_id as string) ?? ''
})

/** 可选画像列表 */
const profileOptions = ref<CustomerProfile[]>([])
/** 画像语境是否由 task_id 推导（推导时不允许手动切换） */
const profileLocked = ref(false)

const page = ref<number>(Number(route.query.page) || 1)
const pageSize = ref<number>(Number(route.query.page_size) || 20)

const list = ref<Enterprise[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)

const stats = reactive({ total: 0, relevant: 0, not_relevant: 0, pending: 0 })

let controller: AbortController | null = null
let searchTimer: number | undefined

function buildQuery(): CompanyQuery {
  const query: CompanyQuery = { page: page.value, page_size: pageSize.value }
  if (filters.company_name.trim()) query.company_name = filters.company_name.trim()
  if (filters.country) query.country = filters.country
  if (filters.industry) query.industry = filters.industry
  if (filters.channel) query.channel = filters.channel
  if (filters.relevance) query.relevance = filters.relevance as RelevanceFilter
  if (filters.grade) query.grade = filters.grade as CompanyGrade
  if (filters.task_id.trim()) query.task_id = filters.task_id.trim()
  if (filters.profile_id) query.profile_id = filters.profile_id
  return query
}

function syncUrl(): void {
  router.replace({
    query: {
      ...(filters.company_name ? { company_name: filters.company_name } : {}),
      ...(filters.country ? { country: filters.country } : {}),
      ...(filters.industry ? { industry: filters.industry } : {}),
      ...(filters.channel ? { channel: filters.channel } : {}),
      ...(filters.relevance ? { relevance: filters.relevance } : {}),
      ...(filters.grade ? { grade: filters.grade } : {}),
      ...(filters.task_id ? { task_id: filters.task_id } : {}),
      ...(filters.profile_id ? { profile_id: filters.profile_id } : {}),
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
    const result = await fetchCompanies(buildQuery(), controller.signal)
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

async function loadStats(): Promise<void> {
  try {
    const result = await fetchCompanyStats({
      task_id: filters.task_id || undefined,
      profile_id: filters.profile_id || undefined
    })
    Object.assign(stats, result)
  } catch {
    Object.assign(stats, { total: 0, relevant: 0, not_relevant: 0, pending: 0 })
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
  filters.company_name = ''
  // 画像语境不随重置清空：清空会让 AI 判断列失去语境
  filters.country = ''
  filters.industry = ''
  filters.channel = ''
  filters.relevance = ''
  filters.grade = ''
  if (!profileLocked.value) filters.task_id = ''
  handleSearch()
}

watch([() => filters.company_name, () => filters.task_id], () => {
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

function asCompany(row: unknown): Enterprise {
  return row as Enterprise
}

/** AI 判断展示：相关 / 不相关 / 待分析 / 分析失败 */
/** AI 判断展示：该画像语境下无分析记录时视为待分析 */
function relevanceKey(company: Enterprise): RelevanceFilter {
  const analysis = company.analysis
  if (!analysis || analysis.status === 'pending') return 'pending'
  if (analysis.status === 'failed') return 'failed'
  return analysis.is_relevant ? 'relevant' : 'not_relevant'
}

function relevanceLabel(company: Enterprise): string {
  return labelOf(RELEVANCE_OPTIONS, relevanceKey(company))
}

function goDetail(company: Enterprise): void {
  router.push({
    path: `/companies/${company.id}`,
    // 带上画像语境，详情页展示同一画像下的判断
    query: filters.profile_id ? { profile_id: filters.profile_id } : {}
  })
}

/**
 * 初始化画像语境
 * 1. 带 task_id 进入 → 取任务的画像并锁定
 * 2. URL 已带 profile_id → 直接使用
 * 3. 都没有 → 默认取第一个画像，页面显式标注当前语境
 */
async function initProfileContext(): Promise<void> {
  try {
    const result = await fetchProfiles({ page: 1, page_size: 100 })
    profileOptions.value = result.list
  } catch {
    profileOptions.value = []
  }

  if (filters.task_id) {
    try {
      const task = await fetchTask(filters.task_id)
      filters.profile_id = task.profile_id
      profileLocked.value = true
    } catch {
      profileLocked.value = false
    }
  }

  if (!filters.profile_id && profileOptions.value.length) {
    filters.profile_id = profileOptions.value[0].id
  }
  syncUrl()
}

const currentProfileName = computed<string>(() => {
  const target = profileOptions.value.find((item) => item.id === filters.profile_id)
  return target?.profile_name ?? filters.profile_id ?? '-'
})

function handleProfileChange(): void {
  handleSearch()
  loadStats()
}

onMounted(async () => {
  await initProfileContext()
  refreshAll()
})
onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="company-page">
    <!-- 标题区 -->
    <section class="company-page__intro app-card">
      <div class="company-page__intro-main">
        <h2 class="company-page__title">
          候选企业库
        </h2>
        <p class="company-page__desc">
          获客任务发现、标准化并全局去重后的企业，经 AI 相关性判断后进入后续获客链路。
        </p>
        <div class="company-page__stats">
          <span class="company-page__stat">
            <i class="company-page__stat-dot is-total" />
            企业总数 <b class="num">{{ stats.total }}</b>
          </span>
          <span class="company-page__stat">
            <i class="company-page__stat-dot is-relevant" />
            AI 有效 <b class="num">{{ stats.relevant }}</b>
          </span>
          <span class="company-page__stat">
            <i class="company-page__stat-dot is-not-relevant" />
            不相关 <b class="num">{{ stats.not_relevant }}</b>
          </span>
          <span class="company-page__stat">
            <i class="company-page__stat-dot is-pending" />
            待分析 <b class="num">{{ stats.pending }}</b>
          </span>
        </div>
      </div>
    </section>

    <!-- 画像语境说明：相关性只在画像语境下成立 -->
    <el-alert
      class="company-page__from-task"
      type="info"
      :closable="false"
      show-icon
      :title="filters.task_id
        ? `当前按获客任务 ${filters.task_id} 筛选，AI 判断基于该任务的画像「${currentProfileName}」`
        : `AI 判断基于画像「${currentProfileName}」`"
      description="同一家企业对不同画像可能得到不同的相关性结论；切换画像会改变下方的 AI 判断与等级。企业实体本身全局唯一。"
    />

    <!-- 筛选 -->
    <section class="company-page__filter app-card">
      <el-select
        v-model="filters.profile_id"
        class="company-page__filter-item"
        placeholder="画像语境"
        :disabled="profileLocked"
        filterable
        @change="handleProfileChange"
      >
        <el-option
          v-for="item in profileOptions"
          :key="item.id"
          :label="item.profile_name"
          :value="item.id"
        />
      </el-select>
      <el-input
        v-model="filters.company_name"
        class="company-page__filter-item"
        placeholder="企业名称 / 官网域名"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="filters.country"
        class="company-page__filter-item"
        placeholder="国家"
        clearable
        filterable
        @change="handleSearch"
      >
        <el-option
          v-for="item in COUNTRY_OPTIONS"
          :key="item.value"
          :label="`${item.label}（${item.value}）`"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.industry"
        class="company-page__filter-item"
        placeholder="行业"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in INDUSTRY_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.channel"
        class="company-page__filter-item"
        placeholder="来源渠道"
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
        v-model="filters.relevance"
        class="company-page__filter-item"
        placeholder="AI 判断"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in RELEVANCE_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.grade"
        class="company-page__filter-item is-narrow"
        placeholder="AI 等级"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in GRADE_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-input
        v-model="filters.task_id"
        class="company-page__filter-item is-narrow"
        placeholder="获客任务编号"
        clearable
      />
      <div class="company-page__filter-actions">
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </section>

    <!-- 列表 -->
    <section class="company-page__table app-card">
      <header class="company-page__table-head">
        <h3 class="company-page__table-title">
          企业列表
        </h3>
        <span class="company-page__table-count">共 <b class="num">{{ total }}</b> 条</span>
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
          class="company-table"
        >
          <template #empty>
            <el-empty
              :image-size="80"
              description="暂无候选企业，可先到获客任务页启动一次企业发现"
            />
          </template>

          <el-table-column
            label="企业名称"
            min-width="260"
            fixed="left"
          >
            <template #default="{ row }">
              <div class="company-cell">
                <div class="company-cell__name">
                  {{ asCompany(row).company_name }}
                </div>
                <div class="company-cell__domain">
                  {{ asCompany(row).domain }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="国家"
            width="110"
          >
            <template #default="{ row }">
              {{ labelOf(COUNTRY_OPTIONS, asCompany(row).country) }}
            </template>
          </el-table-column>

          <el-table-column
            label="行业"
            min-width="150"
          >
            <template #default="{ row }">
              {{ labelOf(INDUSTRY_OPTIONS, asCompany(row).industry) }}
            </template>
          </el-table-column>

          <el-table-column
            label="来源渠道"
            min-width="170"
          >
            <template #default="{ row }">
              <div class="tag-cell">
                <span
                  v-for="item in asCompany(row).discovery_summary.channels.slice(0, 2)"
                  :key="item"
                  class="tag-cell__item"
                >{{ labelOf(CHANNEL_OPTIONS, item) }}</span>
                <span
                  v-if="asCompany(row).discovery_summary.channels.length > 2"
                  class="tag-cell__more"
                >+{{ asCompany(row).discovery_summary.channels.length - 2 }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="来源策略"
            min-width="220"
          >
            <template #default="{ row }">
              <div class="source-cell">
                <span class="source-cell__link">
                  {{ asCompany(row).discovery_summary.latest_strategy_code || '-' }}
                </span>
                <span
                  v-if="asCompany(row).discovery_summary.strategy_count > 1"
                  class="source-cell__count"
                >等 {{ asCompany(row).discovery_summary.strategy_count }} 个策略发现</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="AI 判断"
            width="110"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="chip"
                :class="`is-${relevanceKey(asCompany(row))}`"
              >{{ relevanceLabel(asCompany(row)) }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="AI 等级"
            width="90"
            align="center"
          >
            <template #default="{ row }">
              <span
                v-if="asCompany(row).analysis?.grade"
                class="grade"
              >{{ asCompany(row).analysis?.grade }}</span>
              <span
                v-else
                class="grade-empty"
              >-</span>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asCompany(row).updated_at }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="操作"
            width="120"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                plain
                @click="goDetail(asCompany(row))"
              >
                查看企业
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="company-page__pagination">
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
  </div>
</template>

<style scoped>
.company-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

.company-page__intro {
  padding: 20px var(--space-xl);
}

.company-page__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: 28px;
  color: var(--color-text-primary);
}

.company-page__desc {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.company-page__stats {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-top: 12px;
}

.company-page__stat {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.company-page__stat b {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.company-page__stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.company-page__stat-dot.is-total {
  background: var(--color-primary);
}

.company-page__stat-dot.is-relevant {
  background: var(--color-success);
}

.company-page__stat-dot.is-not-relevant {
  background: var(--color-text-placeholder);
}

.company-page__stat-dot.is-pending {
  background: var(--color-info-main);
}

.company-page__from-task {
  border-radius: var(--radius-card);
}

.company-page__filter {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 14px var(--space-xl);
}

.company-page__filter-item {
  width: 180px;
}

.company-page__filter-item.is-narrow {
  width: 140px;
}

.company-page__filter-actions {
  margin-left: auto;
}

.company-page__table {
  padding: 0 0 var(--space-xl);
}

.company-page__table-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 16px var(--space-xl) 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.company-page__table-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.company-page__table-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.company-page__table-count b {
  color: var(--color-text-primary);
}

.company-table {
  padding: 0 var(--space-xl);
}

.company-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px var(--space-xl) 0;
}

.company-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.company-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

.company-table :deep(.el-table .cell) {
  white-space: nowrap;
}

.company-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-primary-bg);
}

.company-cell__name {
  overflow: hidden;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.company-cell__domain {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.source-cell {
  display: flex;
  flex-direction: column;
}

.source-cell__link {
  overflow: hidden;
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.source-cell__count {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
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

/* AI 判断：明显但不过度视觉化 */
.chip {
  display: inline-block;
  min-width: 52px;
  padding: 0 8px;
  font-size: var(--font-size-xs);
  line-height: 22px;
  text-align: center;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.chip.is-relevant {
  color: var(--color-success);
  background: #eaf7f2;
  border-color: #c6e9dc;
}

.chip.is-not-relevant {
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border-color: var(--color-border);
}

.chip.is-pending {
  color: var(--color-info-text);
  background: var(--color-info-bg);
  border-color: var(--color-info-border);
}

.chip.is-failed {
  color: var(--color-danger);
  background: #fdeced;
  border-color: #f7c9cb;
}

/* AI 等级用 AI 紫，属于 AI 产出（CLAUDE.md 7.3） */
.grade {
  display: inline-block;
  min-width: 24px;
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--color-ai-text);
}

.grade-empty {
  color: var(--color-text-placeholder);
}

.muted-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  white-space: nowrap;
}
</style>
