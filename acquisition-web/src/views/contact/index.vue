<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchContactStats,
  fetchContactTasks,
  fetchContacts,
  retryContactTask,
  verifyContactEmail
} from '@/api/contact'
import { CONTACT_SOURCE_OPTIONS, EMAIL_STATUS_OPTIONS, TARGET_ROLE_OPTIONS, labelOf, labelsOf } from '@/mock/dict'
import type {
  Contact,
  ContactAcquisitionTask,
  ContactQuery,
  ContactSourceType,
  EmailVerificationStatus
} from '@/types/contact'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  keyword: (route.query.keyword as string) ?? '',
  enterprise_name: (route.query.enterprise_name as string) ?? '',
  title: (route.query.title as string) ?? '',
  email_status: (route.query.email_status as string) ?? '',
  source: (route.query.source as string) ?? '',
  enterprise_id: (route.query.enterprise_id as string) ?? ''
})

const page = ref<number>(Number(route.query.page) || 1)
const pageSize = ref<number>(Number(route.query.page_size) || 20)

const list = ref<Contact[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)
const verifyingId = ref('')

const stats = reactive({ total: 0, valid: 0, invalid: 0, pending: 0, ready_enterprises: 0 })

/** 获取失败的企业：通过 Drawer 提供重新获取入口 */
const failedTasks = ref<ContactAcquisitionTask[]>([])
const taskDrawerVisible = ref(false)
const retryingId = ref('')

let controller: AbortController | null = null
let searchTimer: number | undefined

function buildQuery(): ContactQuery {
  const query: ContactQuery = { page: page.value, page_size: pageSize.value }
  if (filters.keyword.trim()) query.keyword = filters.keyword.trim()
  if (filters.enterprise_name.trim()) query.enterprise_name = filters.enterprise_name.trim()
  if (filters.title.trim()) query.title = filters.title.trim()
  if (filters.email_status) query.email_status = filters.email_status as EmailVerificationStatus
  if (filters.source) query.source = filters.source as ContactSourceType
  if (filters.enterprise_id) query.enterprise_id = filters.enterprise_id
  return query
}

function syncUrl(): void {
  router.replace({
    query: {
      ...(filters.keyword ? { keyword: filters.keyword } : {}),
      ...(filters.enterprise_name ? { enterprise_name: filters.enterprise_name } : {}),
      ...(filters.title ? { title: filters.title } : {}),
      ...(filters.email_status ? { email_status: filters.email_status } : {}),
      ...(filters.source ? { source: filters.source } : {}),
      ...(filters.enterprise_id ? { enterprise_id: filters.enterprise_id } : {}),
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
    const result = await fetchContacts(buildQuery(), controller.signal)
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
    Object.assign(stats, await fetchContactStats())
  } catch {
    Object.assign(stats, { total: 0, valid: 0, invalid: 0, pending: 0, ready_enterprises: 0 })
  }
}

async function loadFailedTasks(): Promise<void> {
  try {
    failedTasks.value = await fetchContactTasks({ status: 'failed' })
  } catch {
    failedTasks.value = []
  }
}

function refreshAll(): void {
  loadList()
  loadStats()
  loadFailedTasks()
}

function handleSearch(): void {
  page.value = 1
  syncUrl()
  loadList()
}

function handleReset(): void {
  filters.keyword = ''
  filters.enterprise_name = ''
  filters.title = ''
  filters.email_status = ''
  filters.source = ''
  filters.enterprise_id = ''
  handleSearch()
}

watch([() => filters.keyword, () => filters.enterprise_name, () => filters.title], () => {
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

function asContact(row: unknown): Contact {
  return row as Contact
}

function asTask(row: unknown): ContactAcquisitionTask {
  return row as ContactAcquisitionTask
}

/** 只有 valid 才算可自动开发邮箱 */
function isSendable(contact: Contact): boolean {
  return contact.email_verification.status === 'valid'
}

async function handleVerify(contact: Contact): Promise<void> {
  if (!contact.email) {
    ElMessage.warning('该联系人没有邮箱，无法验证')
    return
  }
  verifyingId.value = contact.id
  try {
    await verifyContactEmail(contact.id)
    ElMessage.success('已重新验证')
    loadList()
    loadStats()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '验证失败')
  } finally {
    verifyingId.value = ''
  }
}

async function handleRetryTask(task: ContactAcquisitionTask): Promise<void> {
  retryingId.value = task.id
  try {
    await retryContactTask(task.id)
    ElMessage.success('已重新获取联系人')
    refreshAll()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重新获取失败')
  } finally {
    retryingId.value = ''
  }
}

function goCompany(contact: Contact): void {
  router.push(`/companies/${contact.enterprise_id}`)
}

const failedCount = computed<number>(() => failedTasks.value.length)

onMounted(refreshAll)
onBeforeUnmount(() => {
  controller?.abort()
  window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="contact-page">
    <!-- 标题区 -->
    <section class="contact-page__intro app-card">
      <div class="contact-page__intro-main">
        <h2 class="contact-page__title">
          联系人中心
        </h2>
        <p class="contact-page__desc">
          企业相关性判断通过后自动获取联系人并完成邮箱验证，只有验证通过的邮箱可进入自动营销。
        </p>
        <div class="contact-page__stats">
          <span class="contact-page__stat">
            <i class="contact-page__stat-dot is-total" />
            联系人总数 <b class="num">{{ stats.total }}</b>
          </span>
          <span class="contact-page__stat">
            <i class="contact-page__stat-dot is-valid" />
            验证通过 <b class="num">{{ stats.valid }}</b>
          </span>
          <span class="contact-page__stat">
            <i class="contact-page__stat-dot is-invalid" />
            验证失败 <b class="num">{{ stats.invalid }}</b>
          </span>
          <span class="contact-page__stat">
            <i class="contact-page__stat-dot is-pending" />
            待验证 <b class="num">{{ stats.pending }}</b>
          </span>
          <span class="contact-page__stat is-ready">
            <i class="contact-page__stat-dot is-ready" />
            可进入待开发 <b class="num">{{ stats.ready_enterprises }}</b> 家企业
          </span>
        </div>
      </div>
    </section>

    <!-- 获取失败提醒 -->
    <el-alert
      v-if="failedCount"
      class="contact-page__alert"
      type="warning"
      :closable="false"
      show-icon
      :title="`有 ${failedCount} 家企业的联系人获取失败`"
      description="失败的企业无法进入待开发客户池，可在获取任务中重新获取。"
    >
      <template #default>
        <el-button
          link
          type="primary"
          @click="taskDrawerVisible = true"
        >
          查看失败任务
        </el-button>
      </template>
    </el-alert>

    <!-- 筛选 -->
    <section class="contact-page__filter app-card">
      <el-input
        v-model="filters.keyword"
        class="contact-page__filter-item"
        placeholder="姓名 / 邮箱"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-input
        v-model="filters.enterprise_name"
        class="contact-page__filter-item"
        placeholder="所属企业"
        clearable
      />
      <el-input
        v-model="filters.title"
        class="contact-page__filter-item"
        placeholder="职位"
        clearable
      />
      <el-select
        v-model="filters.email_status"
        class="contact-page__filter-item"
        placeholder="邮箱验证状态"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in EMAIL_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.source"
        class="contact-page__filter-item"
        placeholder="来源"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="item in CONTACT_SOURCE_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <div class="contact-page__filter-actions">
        <el-button @click="handleReset">
          重置
        </el-button>
      </div>
    </section>

    <!-- 列表 -->
    <section class="contact-page__table app-card">
      <header class="contact-page__table-head">
        <h3 class="contact-page__table-title">
          联系人列表
        </h3>
        <span class="contact-page__table-count">共 <b class="num">{{ total }}</b> 条</span>
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
          class="contact-table"
        >
          <template #empty>
            <el-empty
              :image-size="80"
              description="暂无联系人，企业通过 AI 相关性判断后会自动获取"
            />
          </template>

          <el-table-column
            label="联系人"
            min-width="200"
            fixed="left"
          >
            <template #default="{ row }">
              <div class="contact-cell">
                <div class="contact-cell__name">
                  {{ asContact(row).full_name }}
                </div>
                <div class="contact-cell__sub">
                  {{ asContact(row).department || '-' }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="所属企业"
            min-width="220"
          >
            <template #default="{ row }">
              <span
                class="contact-cell__link"
                @click="goCompany(asContact(row))"
              >{{ asContact(row).enterprise_name }}</span>
              <div class="contact-cell__sub">
                {{ asContact(row).enterprise_domain }}
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="职位"
            min-width="180"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              {{ asContact(row).title || '-' }}
            </template>
          </el-table-column>

          <el-table-column
            label="邮箱"
            min-width="240"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span
                v-if="asContact(row).email"
                class="contact-cell__email"
              >{{ asContact(row).email }}</span>
              <span
                v-else
                class="contact-cell__sub"
              >未获取到邮箱</span>
            </template>
          </el-table-column>

          <el-table-column
            label="邮箱验证"
            width="120"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="chip"
                :class="`is-${asContact(row).email_verification.status}`"
              >
                {{ labelOf(EMAIL_STATUS_OPTIONS, asContact(row).email_verification.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            label="可自动营销"
            width="110"
            align="center"
          >
            <template #default="{ row }">
              <span
                class="sendable"
                :class="{ 'is-yes': isSendable(asContact(row)) }"
              >{{ isSendable(asContact(row)) ? '是' : '否' }}</span>
            </template>
          </el-table-column>

          <el-table-column
            label="来源"
            min-width="160"
          >
            <template #default="{ row }">
              <div class="tag-cell">
                <span
                  v-for="item in asContact(row).source_types"
                  :key="item"
                  class="tag-cell__item"
                >{{ labelOf(CONTACT_SOURCE_OPTIONS, item) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ asContact(row).updated_at }}</span>
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
                plain
                :loading="verifyingId === asContact(row).id"
                :disabled="!asContact(row).email"
                @click="handleVerify(asContact(row))"
              >
                重新验证
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="contact-page__pagination">
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

    <!-- 获取失败任务 -->
    <el-drawer
      v-model="taskDrawerVisible"
      title="联系人获取失败任务"
      size="720px"
    >
      <p class="task-drawer__hint">
        联系人获取任务在企业具备 relevant 判断并选出主画像后自动创建，此处仅提供失败重试。
      </p>
      <el-table
        :data="failedTasks"
        class="task-drawer__table"
      >
        <template #empty>
          <el-empty
            :image-size="70"
            description="暂无失败的获取任务"
          />
        </template>
        <el-table-column
          label="企业"
          min-width="180"
        >
          <template #default="{ row }">
            <div class="contact-cell__name">
              {{ asTask(row).enterprise_name }}
            </div>
            <div class="contact-cell__sub num">
              {{ asTask(row).enterprise_id }}
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="主画像 / 目标角色"
          min-width="220"
        >
          <template #default="{ row }">
            <div>{{ asTask(row).primary_profile_name || asTask(row).primary_profile_id }}</div>
            <div class="contact-cell__sub">
              {{ labelsOf(TARGET_ROLE_OPTIONS, asTask(row).target_roles).join('、') }}
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="失败原因"
          min-width="240"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <span class="task-drawer__reason">{{ asTask(row).failure_reason }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="120"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              plain
              :loading="retryingId === asTask(row).id"
              @click="handleRetryTask(asTask(row))"
            >
              重新获取
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<style scoped>
.contact-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
}

.contact-page__intro {
  padding: 20px var(--space-xl);
}

.contact-page__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  line-height: 28px;
  color: var(--color-text-primary);
}

.contact-page__desc {
  margin: 4px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.contact-page__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: center;
  margin-top: 12px;
}

.contact-page__stat {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.contact-page__stat b {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.contact-page__stat.is-ready {
  padding-left: 20px;
  border-left: 1px solid var(--color-border);
}

.contact-page__stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.contact-page__stat-dot.is-total {
  background: var(--color-primary);
}

.contact-page__stat-dot.is-valid {
  background: var(--color-success);
}

.contact-page__stat-dot.is-invalid {
  background: var(--color-danger);
}

.contact-page__stat-dot.is-pending {
  background: var(--color-info-main);
}

.contact-page__stat-dot.is-ready {
  background: var(--color-primary);
}

.contact-page__alert {
  border-radius: var(--radius-card);
}

.contact-page__filter {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 14px var(--space-xl);
}

.contact-page__filter-item {
  width: 190px;
}

.contact-page__filter-actions {
  margin-left: auto;
}

.contact-page__table {
  padding: 0 0 var(--space-xl);
}

.contact-page__table-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 16px var(--space-xl) 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.contact-page__table-title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.contact-page__table-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.contact-page__table-count b {
  color: var(--color-text-primary);
}

.contact-table {
  padding: 0 var(--space-xl);
}

.contact-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px var(--space-xl) 0;
}

.contact-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.contact-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

.contact-table :deep(.el-table .cell) {
  white-space: nowrap;
}

.contact-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-primary-bg);
}

.contact-cell__name {
  overflow: hidden;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contact-cell__sub {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.contact-cell__link {
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  cursor: pointer;
}

.contact-cell__email {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
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

/* 邮箱验证状态 */
.chip {
  display: inline-block;
  min-width: 60px;
  padding: 0 8px;
  font-size: var(--font-size-xs);
  line-height: 22px;
  text-align: center;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.chip.is-valid {
  color: var(--color-success);
  background: #eaf7f2;
  border-color: #c6e9dc;
}

.chip.is-invalid {
  color: var(--color-danger);
  background: #fdeced;
  border-color: #f7c9cb;
}

.chip.is-pending {
  color: var(--color-info-text);
  background: var(--color-info-bg);
  border-color: var(--color-info-border);
}

.chip.is-catch_all,
.chip.is-unknown {
  color: var(--color-warning);
  background: #fef6e7;
  border-color: #f7dfb0;
}

.sendable {
  font-size: var(--font-size-sm);
  color: var(--color-text-placeholder);
}

.sendable.is-yes {
  font-weight: 600;
  color: var(--color-success);
}

.muted-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  white-space: nowrap;
}

.task-drawer__hint {
  margin: 0 0 14px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.task-drawer__reason {
  font-size: var(--font-size-sm);
  color: var(--color-danger);
}
</style>
