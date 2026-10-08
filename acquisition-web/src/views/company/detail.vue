<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchCompany, fetchCompanyResearch, reanalyzeCompany } from '@/api/company'
import { ApiError } from '@/api/request'
import {
  CHANNEL_OPTIONS,
  COMPANY_TYPE_OPTIONS,
  COUNTRY_OPTIONS,
  INDUSTRY_OPTIONS,
  RELEVANCE_OPTIONS,
  labelOf
} from '@/mock/dict'
import type { Enterprise, RelevanceFilter } from '@/types/company'
import type { ResearchDetail } from '@/types/research'

const route = useRoute()
const router = useRouter()

const companyId = route.params.id as string

/** 画像语境：相关性是「企业 × 画像」的判断，详情页必须明确当前看的是哪个画像 */
const profileId = ref<string>((route.query.profile_id as string) ?? '')

const company = ref<Enterprise | null>(null)
const loading = ref(true)
const error = ref(false)
const analyzing = ref(false)
const research = ref<ResearchDetail | null>(null)
const researchLoading = ref(true)
const researchError = ref('')

let controller: AbortController | null = null
let researchController: AbortController | null = null

const researchStatusLabels: Record<string, string> = {
  not_started: '未开始', received: '已接收', researching: '背调中',
  company_matched: '已匹配企业', completed: '已完成', no_contact: '暂无合适联系人',
  company_not_found: '未找到企业', failed: '失败',
  researching_website: '网站研究中', qualifying: 'AI 判断中',
  fetched: '已获取', empty: '无内容', missing: '无网站',
  qualified: '精准客户', not_qualified: '不精准', review_required: '待人工复核'
}

function statusLabel(status: string): string {
  return researchStatusLabels[status] ?? status
}

function safeUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : undefined
  } catch {
    return undefined
  }
}

async function loadResearch(): Promise<void> {
  researchController?.abort()
  const currentController = new AbortController()
  researchController = currentController
  researchLoading.value = true
  researchError.value = ''
  try {
    research.value = await fetchCompanyResearch(companyId, currentController.signal)
  } catch (err) {
    if (currentController.signal.aborted) return
    research.value = null
    const code = err instanceof ApiError ? err.code : ''
    researchError.value = code === 'service_unavailable' ? '背调服务暂不可用' :
      code === 'upstream_auth_error' ? '背调服务认证失败' : '背调数据读取失败'
  } finally {
    if (!currentController.signal.aborted) researchLoading.value = false
  }
}

async function loadCompany(): Promise<void> {
  controller?.abort()
  controller = new AbortController()

  loading.value = true
  error.value = false
  try {
    company.value = await fetchCompany(companyId, profileId.value || undefined, controller.signal)
    // 未指定画像时，采用后端返回的默认画像语境，避免页面语义不明
    if (!profileId.value) {
      profileId.value = company.value.analysis?.profile_id ?? company.value.analysis_profiles?.[0]?.profile_id ?? ''
    }
  } catch {
    error.value = true
    company.value = null
  } finally {
    loading.value = false
  }
}

const relevanceKey = computed<RelevanceFilter>(() => {
  const analysis = company.value?.analysis
  // 该画像下尚无分析记录，等同于待分析
  if (!analysis || analysis.status === 'pending') return 'pending'
  if (analysis.status === 'failed') return 'failed'
  return analysis.is_relevant ? 'relevant' : 'not_relevant'
})

/** 当前画像名称 */
const currentProfileName = computed<string>(() => {
  const list = company.value?.analysis_profiles ?? []
  return list.find((item) => item.profile_id === profileId.value)?.profile_name ?? profileId.value
})

function handleProfileChange(): void {
  loadCompany()
}

const relevanceLabel = computed<string>(() => labelOf(RELEVANCE_OPTIONS, relevanceKey.value))

async function handleReanalyze(): Promise<void> {
  if (!company.value) return
  if (!profileId.value) {
    ElMessage.warning('请先选择画像语境，相关性判断需要基于具体画像')
    return
  }
  analyzing.value = true
  try {
    // 重新分析会新增一条分析记录，不覆盖历史
    company.value = await reanalyzeCompany(company.value.id, profileId.value)
    ElMessage.success('已重新分析')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '分析失败')
  } finally {
    analyzing.value = false
  }
}

function goList(): void {
  router.push('/companies')
}

onMounted(() => {
  void loadCompany()
  void loadResearch()
})
onBeforeUnmount(() => {
  controller?.abort()
  researchController?.abort()
})
</script>

<template>
  <div class="company-detail">
    <el-skeleton
      v-if="loading"
      :rows="10"
      animated
    />

    <el-result
      v-else-if="error || !company"
      icon="warning"
      title="企业加载失败"
      sub-title="请检查网络后重试"
    >
      <template #extra>
        <el-button
          type="primary"
          @click="loadCompany"
        >
          重新加载
        </el-button>
        <el-button @click="goList">
          返回列表
        </el-button>
      </template>
    </el-result>

    <template v-else>
      <!-- 头部 -->
      <section class="company-detail__head app-card">
        <div class="company-detail__head-main">
          <div class="company-detail__title-row">
            <h2 class="company-detail__title">
              {{ company.company_name }}
            </h2>
            <span
              class="chip"
              :class="`is-${relevanceKey}`"
            >{{ relevanceLabel }}</span>
            <span
              v-if="company.analysis?.grade"
              class="grade-tag"
            >{{ company.analysis.grade }} 类</span>
          </div>
          <div class="company-detail__meta">
            <a
              :href="company.website"
              target="_blank"
              rel="noopener"
              class="company-detail__link"
            >{{ company.domain }}</a>
            <span class="company-detail__divider">·</span>
            <span>{{ labelOf(COUNTRY_OPTIONS, company.country) }}</span>
            <span class="company-detail__divider">·</span>
            <span>{{ labelOf(INDUSTRY_OPTIONS, company.industry) }}</span>
            <span class="company-detail__divider">·</span>
            <span class="num">{{ company.id }}</span>
          </div>
        </div>
        <el-button @click="goList">
          返回列表
        </el-button>
      </section>

      <div class="company-detail__split">
        <!-- 基本信息 -->
        <section class="company-detail__block app-card">
          <header class="company-detail__section-head">
            <h3 class="company-detail__section-title">
              基本信息
            </h3>
          </header>
          <el-descriptions
            :column="1"
            border
          >
            <el-descriptions-item label="发现名称">
              {{ company.company_name }}
            </el-descriptions-item>
            <el-descriptions-item label="标准化名称">
              {{ company.normalized_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="官网">
              <a
                :href="company.website"
                target="_blank"
                rel="noopener"
                class="company-detail__link"
              >{{ company.website || '-' }}</a>
            </el-descriptions-item>
            <el-descriptions-item label="主域名">
              {{ company.domain }}
            </el-descriptions-item>
            <el-descriptions-item label="国家">
              {{ labelOf(COUNTRY_OPTIONS, company.country) }}（{{ company.country }}）
            </el-descriptions-item>
            <el-descriptions-item label="行业">
              {{ labelOf(INDUSTRY_OPTIONS, company.industry) }}
            </el-descriptions-item>
            <el-descriptions-item label="企业类型">
              {{ company.company_type ? labelOf(COMPANY_TYPE_OPTIONS, company.company_type) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="首次发现">
              {{ company.first_discovered_at }}
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <!-- AI 分析 -->
        <section class="company-detail__block app-card">
          <header class="company-detail__section-head">
            <h3 class="company-detail__section-title">
              AI 分析
              <span class="company-detail__ai-tag">AI</span>
            </h3>
            <el-select
              v-model="profileId"
              class="company-detail__profile-select"
              size="small"
              placeholder="画像语境"
              @change="handleProfileChange"
            >
              <el-option
                v-for="item in company.analysis_profiles ?? []"
                :key="item.profile_id"
                :label="item.profile_name"
                :value="item.profile_id"
              />
            </el-select>
            <el-button
              link
              type="primary"
              :loading="analyzing"
              @click="handleReanalyze"
            >
              重新分析
            </el-button>
          </header>

          <div class="ai-block">
            <p class="ai-block__context">
              以下判断基于画像「{{ currentProfileName || '未指定' }}」；同一企业换画像结论可能不同。
            </p>
            <div class="ai-block__row">
              <span class="ai-block__key">is_relevant</span>
              <span
                class="chip"
                :class="`is-${relevanceKey}`"
              >{{ relevanceLabel }}</span>
            </div>
            <div class="ai-block__row">
              <span class="ai-block__key">grade</span>
              <span
                v-if="company.analysis?.grade"
                class="grade-tag"
              >{{ company.analysis.grade }}</span>
              <span
                v-else
                class="ai-block__empty"
              >—（仅相关企业有等级）</span>
            </div>
            <div class="ai-block__row">
              <span class="ai-block__key">分析状态</span>
              <span>{{ company.analysis?.status ?? 'pending' }}</span>
            </div>
            <div class="ai-block__row">
              <span class="ai-block__key">分析时间</span>
              <span>{{ company.analysis?.analyzed_at || '未分析' }}</span>
            </div>

            <div class="ai-block__reason">
              <div class="ai-block__key">
                reason
              </div>
              <p
                v-if="company.analysis?.reason"
                class="ai-block__reason-text"
              >
                {{ company.analysis.reason }}
              </p>
              <p
                v-else-if="company.analysis?.failure_reason"
                class="ai-block__reason-text is-error"
              >
                {{ company.analysis.failure_reason }}
              </p>
              <p
                v-else
                class="ai-block__reason-text is-empty"
              >
                该企业在当前画像下尚未完成 AI 分析，可点击「重新分析」触发。
              </p>
            </div>
          </div>
        </section>
      </div>

      <section class="company-detail__block app-card research-detail">
        <header class="company-detail__section-head">
          <h3 class="company-detail__section-title">
            客户背调与 AI 判断
          </h3>
          <span
            v-if="research && !researchLoading"
            class="company-detail__section-sub"
          >
            Research: {{ statusLabel(research.status) }}
          </span>
        </header>

        <el-skeleton
          v-if="researchLoading"
          :rows="5"
          animated
        />
        <el-result
          v-else-if="researchError"
          icon="warning"
          :title="researchError"
        >
          <template #extra>
            <el-button @click="loadResearch">
              重试
            </el-button>
          </template>
        </el-result>
        <el-empty
          v-else-if="!research || research.status === 'not_started'"
          description="尚未开始客户背调"
          :image-size="70"
        />
        <div
          v-else
          class="research-detail__grid"
        >
          <div class="research-detail__group">
            <h4>Apollo 企业背调</h4>
            <el-descriptions
              :column="1"
              border
            >
              <el-descriptions-item label="背调企业">
                {{ research.company?.apollo_name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="发现名称">
                {{ company.company_name }}
              </el-descriptions-item>
              <el-descriptions-item label="Apollo 域名">
                {{ research.company?.domain || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="匹配分数">
                {{ research.company?.match_score ?? '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="国家">
                {{ research.company?.country || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="行业">
                {{ research.company?.industry || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="员工数">
                {{ research.company?.employee_count ?? '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="LinkedIn">
                <a
                  v-if="safeUrl(research.company?.linkedin_url)"
                  :href="safeUrl(research.company?.linkedin_url)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="company-detail__link"
                >查看公司主页</a>
                <span v-else>-</span>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="research-detail__group">
            <h4>联系人摘要 <span class="company-detail__section-sub">{{ research.contacts.length }} 条</span></h4>
            <el-table
              class="research-detail__contacts-table"
              :data="research.contacts"
              stripe
            >
              <el-table-column
                prop="title"
                label="职位"
                min-width="150"
              >
                <template #default="{ row }">
                  {{ row.title || '-' }}
                </template>
              </el-table-column>
              <el-table-column
                label="有邮箱"
                width="90"
              >
                <template #default="{ row }">
                  {{ row.has_email ? '是' : '否' }}
                </template>
              </el-table-column>
              <el-table-column
                prop="email_status"
                label="邮箱状态"
                min-width="110"
              >
                <template #default="{ row }">
                  {{ row.email_status || '-' }}
                </template>
              </el-table-column>
              <template #empty>
                <el-empty
                  description="暂无联系人摘要"
                  :image-size="55"
                />
              </template>
            </el-table>
            <div class="research-detail__contacts-mobile">
              <div
                v-for="(contact, index) in research.contacts"
                :key="index"
                class="research-detail__contact"
              >
                <div><strong>职位</strong><span>{{ contact.title || '-' }}</span></div>
                <div><strong>有邮箱</strong><span>{{ contact.has_email ? '是' : '否' }}</span></div>
                <div><strong>邮箱状态</strong><span>{{ contact.email_status || '-' }}</span></div>
              </div>
              <el-empty
                v-if="!research.contacts.length"
                description="暂无联系人摘要"
                :image-size="55"
              />
            </div>
          </div>

          <div class="research-detail__group">
            <h4>Website Research <span class="company-detail__section-sub">{{ statusLabel(research.website_research.status) }}</span></h4>
            <el-descriptions
              :column="1"
              border
            >
              <el-descriptions-item label="最终地址">
                <a
                  v-if="safeUrl(research.website_research.final_url)"
                  :href="safeUrl(research.website_research.final_url)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="company-detail__link"
                >{{ research.website_research.final_url }}</a>
                <span v-else>{{ research.website_research.final_url || '-' }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="标题">
                {{ research.website_research.title || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="描述">
                {{ research.website_research.description || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="信号">
                <div>MEAN WELL：{{ research.website_research.signals.meanWellMentioned ? '是' : '否' }}</div>
                <div>直接匹配：{{ research.website_research.signals.directFit ? '是' : '否' }}</div>
                <div>命中词：{{ research.website_research.signals.matchedTerms.join('、') || '-' }}</div>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="research-detail__group">
            <h4>AI Qualification <span class="company-detail__section-sub">{{ statusLabel(research.qualification.status) }}</span></h4>
            <el-descriptions
              :column="1"
              border
            >
              <el-descriptions-item label="判断原因">
                {{ research.qualification.reason || research.qualification.failure_reason || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="客户画像">
                {{ research.qualification.customer_profile || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="推荐产品">
                <div
                  v-for="(item, index) in research.qualification.recommended_products"
                  :key="index"
                >
                  {{ item.name }}<span v-if="item.reason">：{{ item.reason }}</span>
                </div>
                <span v-if="!research.qualification.recommended_products.length">-</span>
              </el-descriptions-item>
              <el-descriptions-item label="风险标记">
                {{ research.qualification.risk_flags.join('、') || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </section>

      <!-- 发现来源 -->
      <section class="company-detail__block app-card">
        <header class="company-detail__section-head">
          <h3 class="company-detail__section-title">
            发现来源
          </h3>
          <span class="company-detail__section-sub">
            共 {{ company.discovery_sources?.length ?? 0 }} 条记录 ·
            来自 {{ company.discovery_summary.strategy_count }} 个搜索策略（企业实体全局唯一）
          </span>
        </header>

        <el-table
          :data="company.discovery_sources ?? []"
          class="source-table"
          stripe
        >
          <template #empty>
            <el-empty
              :image-size="70"
              description="暂无发现来源记录"
            />
          </template>

          <el-table-column
            label="搜索策略"
            min-width="230"
          >
            <template #default="{ row }">
              <span class="source-link">{{ row.strategy_code || '-' }}</span>
              <div class="source-sub num">
                {{ row.strategy_id }}
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="版本 / Provider"
            width="160"
          >
            <template #default="{ row }">
              <span class="num">v{{ row.strategy_version }}</span>
              <span class="source-sub num"> · {{ row.provider }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="渠道"
            width="130"
          >
            <template #default="{ row }">
              <span class="tag-cell__item">{{ labelOf(CHANNEL_OPTIONS, row.channel) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="命中 Query"
            min-width="320"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span class="source-query">{{ row.query }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="发现时间"
            width="170"
          >
            <template #default="{ row }">
              <span class="muted-time">{{ row.discovered_at }}</span>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.company-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-base);
  min-width: 0;
}

.company-detail__head {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 20px var(--space-xl);
}

.company-detail__title-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.company-detail__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.company-detail__meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.company-detail__divider {
  color: var(--color-border);
}

.company-detail__link {
  color: var(--color-primary);
  overflow-wrap: anywhere;
}

.company-detail :deep(.el-descriptions__label) {
  width: 104px;
  white-space: nowrap;
}

.company-detail :deep(.el-descriptions__content) {
  overflow-wrap: anywhere;
}

.company-detail__split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-base);
  align-items: stretch;
}

@media (max-width: 1279px) {
  .company-detail__split {
    grid-template-columns: minmax(0, 1fr);
  }
}

.company-detail__block {
  padding: 18px var(--space-xl) var(--space-xl);
}

.research-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.research-detail__group {
  min-width: 0;
}

.research-detail__group h4 {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 0 0 10px;
  font-size: var(--font-size-sm);
}

.research-detail__contacts-mobile {
  display: none;
}

.research-detail__contact {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.research-detail__contact > div {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 8px;
  padding: 3px 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-sm);
}

.research-detail__contact strong {
  font-weight: 500;
  color: var(--color-text-secondary);
}

@media (max-width: 900px) {
  .research-detail__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 600px) {
  .company-detail__head {
    flex-wrap: wrap;
  }

  .company-detail__head-main {
    min-width: 0;
    width: 100%;
  }

  .company-detail__title-row,
  .company-detail__meta {
    flex-wrap: wrap;
  }

  .company-detail__block {
    padding: 16px;
  }

  .research-detail__contacts-table {
    display: none;
  }

  .research-detail__contacts-mobile {
    display: block;
  }
}

.company-detail__section-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}

.company-detail__section-title {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.company-detail__section-sub {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.company-detail__section-head > .el-button:last-child {
  margin-left: 8px;
}

.company-detail__ai-tag {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

/* AI 分析区：轻量使用 AI 紫 */
.ai-block {
  padding: 14px 16px;
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-card);
}

.company-detail__profile-select {
  width: 190px;
  margin-left: auto;
}

.ai-block__context {
  margin: 0 0 12px;
  font-size: var(--font-size-xs);
  color: var(--color-ai-text);
}

.ai-block__row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.ai-block__key {
  flex: 0 0 84px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.ai-block__empty {
  color: var(--color-text-placeholder);
}

.ai-block__reason {
  padding-top: 10px;
  margin-top: 4px;
  border-top: 1px solid var(--color-ai-border);
}

.ai-block__reason-text {
  margin: 8px 0 0;
  font-size: var(--font-size-sm);
  line-height: 1.75;
  color: var(--color-text-primary);
}

.ai-block__reason-text.is-error {
  color: var(--color-danger);
}

.ai-block__reason-text.is-empty {
  color: var(--color-text-placeholder);
}

/* 状态标签 */
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

.grade-tag {
  padding: 0 8px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 22px;
  color: var(--color-ai-text);
  background: var(--color-card);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

/* 发现来源表 */
.source-table :deep(.el-table__header th.el-table__cell) {
  height: 42px;
  padding: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  background: #f7f9fa;
}

.source-table :deep(.el-table td.el-table__cell) {
  padding: 10px 0;
}

.source-link {
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  cursor: pointer;
}

.source-sub {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.source-query {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.tag-cell__item {
  display: inline-block;
  padding: 1px 8px;
  font-size: var(--font-size-xs);
  line-height: 20px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.muted-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}
</style>
