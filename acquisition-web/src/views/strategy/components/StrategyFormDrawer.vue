<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { generateStrategy, fetchStrategy, regenerateStrategy, updateStrategy } from '@/api/strategy'
import { fetchProfile } from '@/api/profile'
import {
  APPLICATION_SCENARIO_OPTIONS,
  CHANNEL_OPTIONS,
  COMPANY_TYPE_OPTIONS,
  COUNTRY_OPTIONS,
  INDUSTRY_OPTIONS,
  LANGUAGE_OPTIONS,
  PRODUCT_LINE_OPTIONS,
  labelOf,
  labelsOf
} from '@/mock/dict'
import type { CustomerProfile } from '@/types/profile'
import { ApiError } from '@/api/request'
import {
  ACTIVATE_HINT,
  ACTIVE_EDIT_HINT,
  STRATEGY_VERSION_CONFLICT,
  canActivate
} from '@/types/strategy'
import type { ChannelSearchStrategy, SearchStrategy, StrategyStatus } from '@/types/strategy'

/** generate = AI 生成新策略；edit = 编辑已有策略；regenerate = 基于画像重新生成 */
type DrawerMode = 'generate' | 'edit' | 'regenerate'

const props = defineProps<{
  modelValue: boolean
  mode: DrawerMode
  /** generate 模式必填 */
  profileId?: string | null
  /** edit / regenerate 模式必填 */
  strategyId?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved'): void
}>()

/** idle → loading/generating → ready | error */
const phase = ref<'idle' | 'loading' | 'generating' | 'ready' | 'error'>('idle')
const errorMessage = ref('')
const submitting = ref(false)

const strategy = ref<SearchStrategy | null>(null)
const channels = ref<ChannelSearchStrategy[]>([])
const profile = ref<CustomerProfile | null>(null)

const title = computed<string>(() => {
  if (props.mode === 'edit') return '编辑搜索策略'
  if (props.mode === 'regenerate') return '重新生成搜索策略'
  return 'AI 生成搜索策略'
})

const isGenerating = computed<boolean>(() => phase.value === 'generating')

/** 重新生成 / 对已有策略再次生成时，展示的是未落库的新版本预览 */
const isPreview = computed<boolean>(() => props.mode !== 'edit')

function clonePlain<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/**
 * 未保存标记
 * 统一维护一个 dirty 状态，不依赖 DOM 或逐字段临时比对：
 *   - generate / regenerate 生成成功即视为存在未保存的 AI 结果
 *   - edit 模式下由用户改动触发
 *   - loading / generating / error 阶段不置脏
 *   - 保存成功后复位
 */
const dirty = ref(false)
/** 数据装载期间的改动不计入 dirty */
let trackChanges = false

watch(
  channels,
  () => {
    if (trackChanges) dirty.value = true
  },
  { deep: true }
)

function channelLabel(channel: string): string {
  return labelOf(CHANNEL_OPTIONS, channel)
}

function totalQueries(): number {
  return channels.value.reduce((sum, item) => sum + item.queries.length, 0)
}

async function loadProfile(profileId: string): Promise<void> {
  try {
    profile.value = await fetchProfile(profileId)
  } catch {
    profile.value = null
  }
}

/** 进入 Drawer 时按模式装载数据 */
async function bootstrap(): Promise<void> {
  trackChanges = false
  dirty.value = false
  strategy.value = null
  channels.value = []
  profile.value = null
  errorMessage.value = ''

  try {
    if (props.mode === 'generate') {
      if (!props.profileId) throw new Error('缺少来源画像')
      phase.value = 'generating'
      await loadProfile(props.profileId)
      const result = await generateStrategy({ profile_id: props.profileId })
      strategy.value = result
      channels.value = clonePlain(result.channel_strategies)
    } else if (props.mode === 'regenerate') {
      if (!props.strategyId) throw new Error('缺少策略 ID')
      phase.value = 'generating'
      const result = await regenerateStrategy(props.strategyId)
      strategy.value = result
      channels.value = clonePlain(result.channel_strategies)
      await loadProfile(result.profile_id)
    } else {
      if (!props.strategyId) throw new Error('缺少策略 ID')
      phase.value = 'loading'
      const result = await fetchStrategy(props.strategyId)
      strategy.value = result
      channels.value = clonePlain(result.channel_strategies)
      await loadProfile(result.profile_id)
    }
    phase.value = 'ready'
    await nextTick()
    trackChanges = true
    // AI 生成结果本身就是尚未保存的内容；纯编辑模式等待用户改动
    dirty.value = props.mode !== 'edit'
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '生成失败'
    phase.value = 'error'
    trackChanges = false
    dirty.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) bootstrap()
  }
)

function close(): void {
  trackChanges = false
  dirty.value = false
  emit('update:modelValue', false)
}

/** 存在未保存内容时二次确认；loading / generating / error 阶段不拦截 */
async function attemptClose(): Promise<void> {
  if (!dirty.value || phase.value !== 'ready') {
    close()
    return
  }
  try {
    await ElMessageBox.confirm(
      '当前搜索策略存在未保存的修改，关闭后这些内容将丢失，确定放弃吗？',
      '放弃未保存的修改',
      { confirmButtonText: '放弃修改', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  close()
}

/** el-drawer 的关闭拦截（点遮罩、按 ESC、右上角 X 都会走这里） */
function handleBeforeClose(done: () => void): void {
  if (!dirty.value || phase.value !== 'ready') {
    close()
    done()
    return
  }
  ElMessageBox.confirm(
    '当前搜索策略存在未保存的修改，关闭后这些内容将丢失，确定放弃吗？',
    '放弃未保存的修改',
    { confirmButtonText: '放弃修改', cancelButtonText: '取消', type: 'warning' }
  )
    .then(() => {
      close()
      done()
    })
    .catch(() => undefined)
}

/* ---------------- Query 编辑：仅改本地草稿，保存时统一提交 ---------------- */

let localSeed = 0
function addQuery(channel: ChannelSearchStrategy): void {
  localSeed += 1
  channel.queries.push({
    id: `NEW-${localSeed}`,
    query_text: '',
    country_code: channel.target_countries[0],
    language: undefined,
    enabled: true
  })
}

function removeQuery(channel: ChannelSearchStrategy, index: number): void {
  channel.queries.splice(index, 1)
}

/* ---------------- 保存 ---------------- */

async function save(status: StrategyStatus): Promise<void> {
  if (!strategy.value) return

  // 空文本 Query 属于无意义配置，提交前统一剔除（草稿同样处理）
  const cleaned: ChannelSearchStrategy[] = channels.value.map((channel) => ({
    ...channel,
    queries: channel.queries.filter((query) => query.query_text.trim().length > 0)
  }))

  /*
   * 只要最终状态仍是 active，就必须满足 active 的完整运行条件，
   * 杜绝「原本 active → 关掉全部渠道 → 保存 → 仍是 active」的绕过路径。
   * 保存为 draft 允许配置不完整。
   */
  if (status === 'active' && !canActivate(cleaned)) {
    const isEditingActive = props.mode === 'edit' && strategy.value.status === 'active'
    ElMessage.warning(isEditingActive ? ACTIVE_EDIT_HINT : ACTIVATE_HINT)
    return
  }

  submitting.value = true
  try {
    await updateStrategy(strategy.value.id, {
      channel_strategies: cleaned,
      status,
      // 回传预览版本：重新生成得到的 version + 1 在此刻才真正落库
      version: strategy.value.version,
      // 乐观锁基准：服务端版本与之不一致则拒绝保存
      base_version: strategy.value.base_version ?? strategy.value.version
    })
    ElMessage.success(status === 'active' ? '已保存并启用' : '已保存')
    emit('saved')
    close()
  } catch (err) {
    // 版本冲突：不覆盖、不合并，保留当前 Drawer 内容，交由用户决定
    if (err instanceof ApiError && err.code === STRATEGY_VERSION_CONFLICT) {
      await ElMessageBox.alert(err.message, '版本冲突', {
        confirmButtonText: '我知道了',
        type: 'warning'
      })
      return
    }
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="820px"
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!-- 来源画像 -->
    <section
      v-if="profile"
      class="strategy-form__profile"
    >
      <div class="strategy-form__profile-head">
        <span class="strategy-form__profile-label">来源客户画像</span>
        <span class="strategy-form__profile-name">{{ profile.profile_name }}</span>
      </div>
      <div class="strategy-form__profile-grid">
        <div class="strategy-form__profile-item">
          <span class="strategy-form__profile-key">目标行业</span>
          <span>{{ labelsOf(INDUSTRY_OPTIONS, profile.target_industries).join('、') || '-' }}</span>
        </div>
        <div class="strategy-form__profile-item">
          <span class="strategy-form__profile-key">国家</span>
          <span>{{ labelsOf(COUNTRY_OPTIONS, profile.target_countries).join('、') || '-' }}</span>
        </div>
        <div class="strategy-form__profile-item">
          <span class="strategy-form__profile-key">企业类型</span>
          <span>{{ labelsOf(COMPANY_TYPE_OPTIONS, profile.company_types).join('、') || '-' }}</span>
        </div>
        <div class="strategy-form__profile-item">
          <span class="strategy-form__profile-key">产品线</span>
          <span>{{ labelsOf(PRODUCT_LINE_OPTIONS, profile.product_lines).join('、') || '-' }}</span>
        </div>
        <div class="strategy-form__profile-item is-full">
          <span class="strategy-form__profile-key">应用场景</span>
          <span>
            {{ labelsOf(APPLICATION_SCENARIO_OPTIONS, profile.application_scenarios).join('、') || '-' }}
          </span>
        </div>
      </div>
    </section>

    <!-- AI 生成中 -->
    <section
      v-if="isGenerating"
      class="strategy-form__generating"
    >
      <div class="strategy-form__generating-badge">
        AI
      </div>
      <p class="strategy-form__generating-text">
        AI 正在根据画像生成搜索策略…
      </p>
      <p class="strategy-form__generating-hint">
        正在解析目标行业、国家、企业类型、产品线、应用场景与判断条件，生成各渠道搜索 Query
      </p>
      <el-skeleton
        :rows="5"
        animated
        class="strategy-form__skeleton"
      />
    </section>

    <!-- 编辑态读取中 -->
    <el-skeleton
      v-else-if="phase === 'loading'"
      :rows="8"
      animated
    />

    <!-- 生成 / 读取失败 -->
    <el-result
      v-else-if="phase === 'error'"
      icon="warning"
      title="生成失败"
      :sub-title="errorMessage || '请稍后重试'"
    >
      <template #extra>
        <el-button
          type="primary"
          @click="bootstrap"
        >
          重新生成
        </el-button>
      </template>
    </el-result>

    <!-- 策略编辑区 -->
    <section
      v-else-if="phase === 'ready'"
      class="strategy-form__body"
    >
      <div class="strategy-form__summary">
        <span class="strategy-form__ai-tag">AI</span>
        <span>
          共生成 <b class="num">{{ channels.length }}</b> 个渠道、<b class="num">{{ totalQueries() }}</b> 条 Query，可逐条调整后保存
        </span>
        <span
          v-if="strategy"
          class="strategy-form__version"
        >v{{ strategy.version }}</span>
      </div>

      <el-alert
        v-if="isPreview"
        class="strategy-form__preview-tip"
        type="warning"
        :closable="false"
        show-icon
        title="这是尚未生效的新版本预览"
        description="保存之前，原策略继续有效；已创建的获客任务始终保留原版本，不受本次重新生成影响。"
      />

      <div
        v-for="channel in channels"
        :key="channel.channel"
        class="channel-card"
        :class="{ 'is-off': !channel.enabled }"
      >
        <header class="channel-card__head">
          <div class="channel-card__title">
            <span class="channel-card__name">{{ channelLabel(channel.channel) }}</span>
            <span class="channel-card__count">{{ channel.queries.length }} 条 Query</span>
          </div>
          <el-switch
            v-model="channel.enabled"
            active-text="启用"
            inactive-text="停用"
          />
        </header>

        <el-input
          v-model="channel.strategy_summary"
          type="textarea"
          :rows="2"
          class="channel-card__summary"
          placeholder="该渠道的策略说明"
        />

        <div class="channel-card__queries">
          <div
            v-for="(query, index) in channel.queries"
            :key="query.id"
            class="query-row"
            :class="{ 'is-off': !query.enabled }"
          >
            <el-input
              v-model="query.query_text"
              class="query-row__text"
              placeholder="搜索 Query"
            />
            <span class="query-row__country">
              {{ query.country_code ? labelOf(COUNTRY_OPTIONS, query.country_code) : '不限' }}
            </span>
            <el-select
              v-model="query.language"
              class="query-row__lang"
              placeholder="语言"
              size="small"
              clearable
              filterable
              allow-create
              default-first-option
            >
              <el-option
                v-for="item in LANGUAGE_OPTIONS"
                :key="item.value"
                :label="item.value"
                :value="item.value"
              />
            </el-select>
            <el-switch
              v-model="query.enabled"
              size="small"
            />
            <el-button
              link
              class="query-row__remove"
              @click="removeQuery(channel, index)"
            >
              删除
            </el-button>
          </div>

          <el-button
            text
            type="primary"
            @click="addQuery(channel)"
          >
            + 新增 Query
          </el-button>
        </div>
      </div>
    </section>

    <template #footer>
      <div
        v-if="phase === 'ready'"
        class="strategy-form__footer"
      >
        <el-button @click="attemptClose">
          取消
        </el-button>
        <el-button
          :loading="submitting"
          @click="save(mode === 'edit' && strategy ? strategy.status : 'draft')"
        >
          {{ mode === 'edit' ? '保存' : '保存为草稿' }}
        </el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="save('active')"
        >
          保存并启用
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
/* ---------- 来源画像 ---------- */
.strategy-form__profile {
  padding: 14px 16px;
  margin-bottom: 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.strategy-form__profile-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.strategy-form__profile-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.strategy-form__profile-name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.strategy-form__profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 6px 20px;
  margin-top: 10px;
}

.strategy-form__profile-item {
  display: flex;
  gap: 8px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.strategy-form__profile-item.is-full {
  grid-column: 1 / -1;
}

.strategy-form__profile-key {
  flex: 0 0 64px;
  color: var(--color-text-secondary);
}

/* ---------- AI 生成中 ---------- */
.strategy-form__generating {
  padding: 24px 20px;
  text-align: center;
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-card);
}

.strategy-form__generating-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--color-text-inverse);
  background: var(--color-ai);
  border-radius: 50%;
}

.strategy-form__generating-text {
  margin: 12px 0 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-ai-text);
}

.strategy-form__generating-hint {
  margin: 6px 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.strategy-form__skeleton {
  margin-top: 18px;
  text-align: left;
}

/* ---------- 生成结果 ---------- */
.strategy-form__summary {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 10px 14px;
  margin-bottom: 14px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-base);
}

.strategy-form__ai-tag {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-card);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

.strategy-form__version {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* ---------- 渠道卡片 ---------- */
.channel-card {
  padding: 14px 16px;
  margin-bottom: 14px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.channel-card.is-off {
  background: var(--color-bg);
}

.channel-card.is-off .channel-card__name {
  color: var(--color-text-secondary);
}

.channel-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.channel-card__title {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.channel-card__name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.channel-card__count {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.channel-card__summary {
  margin-top: 10px;
}

.channel-card__queries {
  margin-top: 10px;
}

/* ---------- Query 行 ---------- */
.query-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.query-row.is-off .query-row__text :deep(.el-input__inner) {
  color: var(--color-text-placeholder);
}

.query-row__text {
  flex: 1;
  min-width: 0;
}

.query-row__country {
  flex: 0 0 64px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  text-align: center;
}

.query-row__lang {
  flex: 0 0 88px;
}

.query-row__remove {
  flex: 0 0 auto;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.query-row__remove:hover {
  color: var(--color-danger);
}

.strategy-form__preview-tip {
  margin-bottom: 14px;
}

.strategy-form__footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
</style>
