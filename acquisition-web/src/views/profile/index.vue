<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProfileFormDrawer from './components/ProfileFormDrawer.vue'
import ProfileDetailDrawer from './components/ProfileDetailDrawer.vue'
import { fetchProfiles, updateProfileStatus } from '@/api/profile'
import {
  COUNTRY_OPTIONS,
  INDUSTRY_OPTIONS,
  PRIORITY_OPTIONS,
  PRODUCT_LINE_OPTIONS,
  STATUS_OPTIONS,
  COMPANY_SIZE_OPTIONS,
  COMPANY_TYPE_OPTIONS,
  labelOf,
  labelsOf
} from '@/mock/dict'
import type { Option } from '@/types/common'
import type { CustomerProfile, ProfilePriority, ProfileQuery } from '@/types/profile'

const route = useRoute()
const router = useRouter()

/** 筛选条件：初始值从 URL query 还原（CLAUDE.md 8.4） */
const filters = reactive({
  profile_name: (route.query.profile_name as string) ?? '',
  target_industry: (route.query.target_industry as string) ?? '',
  target_country: (route.query.target_country as string) ?? '',
  status: (route.query.status as string) ?? ''
})

const page = ref<number>(Number(route.query.page) || 1)
const pageSize = ref<number>(Number(route.query.page_size) || 20)

const list = ref<CustomerProfile[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)

/** 顶部轻量概览：复用列表接口的 total 字段，不新增接口语义 */
const stats = reactive({ total: 0, enabled: 0, disabled: 0 })

const formVisible = ref(false)
const detailVisible = ref(false)
const currentProfile = ref<CustomerProfile | null>(null)

/** 快速切换筛选时取消上一请求，防止旧响应覆盖新结果 */
let controller: AbortController | null = null
let searchTimer: number | undefined

function buildQuery(): ProfileQuery {
  const query: ProfileQuery = { page: page.value, page_size: pageSize.value }
  if (filters.profile_name.trim()) query.profile_name = filters.profile_name.trim()
  if (filters.target_industry) query.target_industry = filters.target_industry
  if (filters.target_country) query.target_country = filters.target_country
  if (filters.status) query.is_enabled = filters.status === 'enabled'
  return query
}

/** 筛选状态同步到 URL，保证刷新与分享可还原 */
function syncUrl(): void {
  router.replace({
    query: {
      ...(filters.profile_name ? { profile_name: filters.profile_name } : {}),
      ...(filters.target_industry ? { target_industry: filters.target_industry } : {}),
      ...(filters.target_country ? { target_country: filters.target_country } : {}),
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
    const result = await fetchProfiles(buildQuery(), controller.signal)
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

/** 概览计数：只取 total，page_size 取 1 以减少传输；失败不影响主列表 */
async function loadStats(): Promise<void> {
  try {
    const [all, enabled, disabled] = await Promise.all([
      fetchProfiles({ page: 1, page_size: 1 }),
      fetchProfiles({ page: 1, page_size: 1, is_enabled: true }),
      fetchProfiles({ page: 1, page_size: 1, is_enabled: false })
    ])
    stats.total = all.total
    stats.enabled = enabled.total
    stats.disabled = disabled.total
  } catch {
    stats.total = 0
    stats.enabled = 0
    stats.disabled = 0
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
  filters.target_industry = ''
  filters.target_country = ''
  filters.status = ''
  handleSearch()
}

/** 关键词防抖 400ms */
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

/**
 * el-table 插槽的 row 类型是 DefaultRow（Record<PropertyKey, any>），
 * 统一在此收窄为 CustomerProfile，避免在模板里散落类型断言。
 */
function asProfile(row: unknown): CustomerProfile {
  return row as CustomerProfile
}

/** 多值列：只展示前 2 项，其余以 +N 收纳 */
function visibleLabels(options: Option[], values: string[] | undefined): string[] {
  return labelsOf(options, values).slice(0, 2)
}

function restCount(values: string[] | undefined): number {
  return Math.max((values?.length ?? 0) - 2, 0)
}

function allLabels(options: Option[], values: string[] | undefined): string {
  return labelsOf(options, values).join('、') || '-'
}

/** 优先级标签样式：高=品牌主色，中=信息蓝，低=中性（不占用错误/警告色） */
function priorityClass(priority: ProfilePriority): string {
  return `is-${priority}`
}

function openCreate(): void {
  currentProfile.value = null
  formVisible.value = true
}

function openEdit(row: CustomerProfile): void {
  currentProfile.value = row
  formVisible.value = true
}

function openDetail(row: CustomerProfile): void {
  currentProfile.value = row
  detailVisible.value = true
}

async function toggleStatus(row: CustomerProfile): Promise<void> {
  const nextEnabled = !row.is_enabled
  const action = nextEnabled ? '启用' : '暂停'
  try {
    await ElMessageBox.confirm(
      `确定${action}画像「${row.profile_name}」吗？${nextEnabled ? '' : '暂停后该画像不再参与企业发现。'}`,
      `${action}画像`,
      {
        confirmButtonText: action,
        cancelButtonText: '取消',
        type: nextEnabled ? 'info' : 'warning'
      }
    )
  } catch {
    return
  }

  try {
    await updateProfileStatus(row.id, { is_enabled: nextEnabled })
    ElMessage.success(`已${action}`)
    refreshAll()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败')
  }
}

/** 生成搜索策略：带画像 id 跳到搜索策略模块（该模块尚未开发） */
function goGenerateStrategy(row: CustomerProfile): void {
  router.push({
    path: '/search-strategies',
    query: { profile_id: row.id, action: 'generate' }
  })
}

/** 次级操作下拉 */
function handleCommand(command: string, row: CustomerProfile): void {
  if (command === 'edit') openEdit(row)
  if (command === 'status') toggleStatus(row)
}

function handleSaved(): void {
  refreshAll()
}

onMounted(refreshAll)
onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="profile-page">
    <!-- 标题区：标题 + 说明 + 轻量概览 + 主操作 -->
    <section class="profile-page__intro app-card">
      <div class="profile-page__intro-main">
        <h2 class="profile-page__title">
          客户画像
        </h2>
        <p class="profile-page__desc">
          定义目标客户特征，用于指导 AI 搜索、企业发现与后续企业相关性判断。
        </p>
        <div class="profile-page__stats">
          <span class="profile-page__stat">
            <i class="profile-page__stat-dot is-total" />
            总画像
            <b class="num">{{ stats.total }}</b>
          </span>
          <span class="profile-page__stat">
            <i class="profile-page__stat-dot is-enabled" />
            启用中
            <b class="num">{{ stats.enabled }}</b>
          </span>
          <span class="profile-page__stat">
            <i class="profile-page__stat-dot is-disabled" />
            已暂停
            <b class="num">{{ stats.disabled }}</b>
          </span>
        </div>
      </div>
      <el-button
        type="primary"
        @click="openCreate"
      >
        <el-icon><Plus /></el-icon>
        新建客户画像
      </el-button>
    </section>

    <!-- 筛选工具条 -->
    <section class="profile-page__filter app-card">
      <el-input
        v-model="filters.profile_name"
        class="profile-page__filter-item"
        placeholder="搜索画像名称"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="filters.target_industry"
        class="profile-page__filter-item"
        placeholder="目标行业"
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
        v-model="filters.target_country"
        class="profile-page__filter-item"
        placeholder="目标国家"
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
        v-model="filters.status"
        class="profile-page__filter-item"
        placeholder="状态"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <div class="profile-page__filter-actions">
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </section>

    <!-- 列表模块 -->
    <section class="profile-page__table app-card">
      <header class="profile-page__table-head">
        <h3 class="profile-page__table-title">
          画像列表
        </h3>
        <span class="profile-page__table-count">共 <b class="num">{{ total }}</b> 条</span>
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
          class="profile-table"
        >
          <template #empty>
            <el-empty
              :image-size="80"
              description="暂无客户画像，点击右上角「新建客户画像」开始定义目标客户"
            />
          </template>

          <!-- 主信息列 -->
          <el-table-column
            label="画像名称"
            min-width="220"
            fixed="left"
          >
            <template #default="{ row }">
              <div class="profile-cell">
                <div class="profile-cell__name">
                  {{ asProfile(row).profile_name }}
                </div>
                <div class="profile-cell__meta">
                  <span class="profile-cell__id num">{{ asProfile(row).id }}</span>
                  <span class="profile-cell__divider">·</span>
                  <span>{{ labelOf(COMPANY_SIZE_OPTIONS, asProfile(row).company_size) }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="目标行业"
            min-width="200"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="allLabels(INDUSTRY_OPTIONS, asProfile(row).target_industries)"
                placement="top"
                :disabled="!asProfile(row).target_industries.length"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleLabels(INDUSTRY_OPTIONS, asProfile(row).target_industries)"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restCount(asProfile(row).target_industries)"
                    class="tag-cell__more"
                  >+{{ restCount(asProfile(row).target_industries) }}</span>
                  <span
                    v-if="!asProfile(row).target_industries.length"
                    class="tag-cell__empty"
                  >-</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="目标国家"
            min-width="130"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="allLabels(COUNTRY_OPTIONS, asProfile(row).target_countries)"
                placement="top"
                :disabled="!asProfile(row).target_countries.length"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleLabels(COUNTRY_OPTIONS, asProfile(row).target_countries)"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restCount(asProfile(row).target_countries)"
                    class="tag-cell__more"
                  >+{{ restCount(asProfile(row).target_countries) }}</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="企业类型"
            min-width="190"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="allLabels(COMPANY_TYPE_OPTIONS, asProfile(row).company_types)"
                placement="top"
                :disabled="!asProfile(row).company_types.length"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleLabels(COMPANY_TYPE_OPTIONS, asProfile(row).company_types)"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restCount(asProfile(row).company_types)"
                    class="tag-cell__more"
                  >+{{ restCount(asProfile(row).company_types) }}</span>
                  <span
                    v-if="!asProfile(row).company_types.length"
                    class="tag-cell__empty"
                  >-</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="匹配产品线"
            min-width="190"
          >
            <template #default="{ row }">
              <el-tooltip
                :content="allLabels(PRODUCT_LINE_OPTIONS, asProfile(row).product_lines)"
                placement="top"
                :disabled="!asProfile(row).product_lines.length"
              >
                <div class="tag-cell">
                  <span
                    v-for="item in visibleLabels(PRODUCT_LINE_OPTIONS, asProfile(row).product_lines)"
                    :key="item"
                    class="tag-cell__item"
                  >{{ item }}</span>
                  <span
                    v-if="restCount(asProfile(row).product_lines)"
                    class="tag-cell__more"
                  >+{{ restCount(asProfile(row).product_lines) }}</span>
                  <span
                    v-if="!asProfile(row).product_lines.length"
                    class="tag-cell__empty"
                  >-</span>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column
            label="每日配额"
            width="110"
            align="right"
          >
            <template #default="{ row }">
              <span class="quota">
                <b class="quota__value num">{{ asProfile(row).daily_quota }}</b>
                <span class="quota__unit">家/日</span>
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="优先级"
            width="96"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="chip"
                :class="priorityClass(asProfile(row).priority)"
              >
                {{ labelOf(PRIORITY_OPTIONS, asProfile(row).priority) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="状态"
            width="96"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="chip"
                :class="asProfile(row).is_enabled ? 'is-enabled' : 'is-disabled'"
              >
                {{ asProfile(row).is_enabled ? '启用' : '暂停' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asProfile(row).updated_at }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="操作"
            width="230"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  @click="goGenerateStrategy(asProfile(row))"
                >
                  生成搜索策略
                </el-button>
                <el-button
                  link
                  class="row-actions__link"
                  @click="openDetail(asProfile(row))"
                >
                  查看
                </el-button>
                <el-dropdown
                  trigger="click"
                  @command="(command: string) => handleCommand(command, asProfile(row))"
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
                      <el-dropdown-item command="status">
                        {{ asProfile(row).is_enabled ? '暂停' : '启用' }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="profile-page__pagination">
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

    <ProfileFormDrawer
      v-model="formVisible"
      :profile="currentProfile"
      @saved="handleSaved"
    />
    <ProfileDetailDrawer
      v-model="detailVisible"
      :profile="currentProfile"
    />
  </div>
</template>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

/* ---------- 标题区 ---------- */
.profile-page__intro {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 20px var(--space-xl);
}

.profile-page__intro-main {
  min-width: 0;
}

.profile-page__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: 28px;
  color: var(--color-text-primary);
}

.profile-page__desc {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.profile-page__stats {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-top: 12px;
}

.profile-page__stat {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.profile-page__stat b {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.profile-page__stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.profile-page__stat-dot.is-total {
  background: var(--color-primary);
}

.profile-page__stat-dot.is-enabled {
  background: var(--color-success);
}

.profile-page__stat-dot.is-disabled {
  background: var(--color-text-placeholder);
}

/* ---------- 筛选工具条 ---------- */
.profile-page__filter {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 14px var(--space-xl);
}

.profile-page__filter-item {
  width: 200px;
}

.profile-page__filter-actions {
  margin-left: auto;
}

/* ---------- 列表模块 ---------- */
.profile-page__table {
  padding: 0 0 var(--space-xl);
}

.profile-page__table-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 16px var(--space-xl) 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.profile-page__table-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.profile-page__table-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.profile-page__table-count b {
  color: var(--color-text-primary);
}

.profile-table {
  padding: 0 var(--space-xl);
}

.profile-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px var(--space-xl) 0;
}

/* ---------- 表头与行 ---------- */
.profile-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.profile-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

/* 单元格内容一律单行，避免行高跳动 */
.profile-table :deep(.el-table .cell) {
  white-space: nowrap;
}

.profile-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-primary-bg);
}

.profile-table :deep(.el-table__border-left-patch),
.profile-table :deep(.el-table::before) {
  display: none;
}

/* ---------- 主信息列 ---------- */
.profile-cell__name {
  overflow: hidden;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-cell__meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.profile-cell__divider {
  color: var(--color-border);
}

/* ---------- 多值列 ---------- */
/* 多值列单行展示，放不下由 +N 与 tooltip 兜底，不换行 */
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
  white-space: nowrap;
  font-size: var(--font-size-xs);
  line-height: 20px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.tag-cell__more {
  flex: 0 0 auto;
  padding: 1px 6px;
  white-space: nowrap;
  font-size: var(--font-size-xs);
  line-height: 20px;
  color: var(--color-text-secondary);
  background: transparent;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
}

.tag-cell__empty {
  color: var(--color-text-placeholder);
}

/* ---------- 配额 ---------- */
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

/* ---------- 轻量标签：优先级 / 状态 ---------- */
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

/* 优先级：高=品牌绿 / 中=信息蓝 / 低=中性，不占用错误与警告色 */
.chip.is-high {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  border-color: #cddcd9;
}

.chip.is-medium {
  color: var(--color-info-text);
  background: var(--color-info-bg);
  border-color: var(--color-info-border);
}

.chip.is-low {
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border-color: var(--color-border);
}

.chip.is-enabled {
  color: var(--color-success);
  background: #eaf7f2;
  border-color: #c6e9dc;
}

.chip.is-disabled {
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border-color: var(--color-border);
}

/* ---------- 更新时间弱化 ---------- */
.muted-time {
  font-size: var(--font-size-xs);
  white-space: nowrap;
  color: var(--color-text-placeholder);
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
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.row-actions__link:hover {
  color: var(--color-primary);
}

.row-actions__more {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 2px;
  align-items: center;
  white-space: nowrap;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.row-actions__more:hover {
  color: var(--color-primary);
}
</style>
