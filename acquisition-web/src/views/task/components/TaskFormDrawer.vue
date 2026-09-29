<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { createTask } from '@/api/task'
import { fetchStrategies, fetchStrategy } from '@/api/strategy'
import { CHANNEL_OPTIONS, COUNTRY_OPTIONS, labelOf, labelsOf } from '@/mock/dict'
import { canActivate } from '@/types/strategy'
import type { SearchStrategy } from '@/types/strategy'

const props = defineProps<{
  modelValue: boolean
  /** 从搜索策略跳转进入时带入 */
  strategyId?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', taskId: string): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const loading = ref(false)

/** 可选策略：只取 active，未从策略页跳转时供用户选择 */
const strategyOptions = ref<SearchStrategy[]>([])
const strategy = ref<SearchStrategy | null>(null)

const form = ref<{ task_name: string; strategy_id: string }>({
  task_name: '',
  strategy_id: ''
})

const rules: FormRules = {
  task_name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    { min: 2, max: 60, message: '长度在 2 到 60 个字符', trigger: 'blur' }
  ],
  strategy_id: [{ required: true, message: '请选择搜索策略', trigger: 'change' }]
}

/** 有效渠道：启用且含有效 Query */
const enabledChannels = computed(() =>
  (strategy.value?.channel_strategies ?? []).filter(
    (channel) =>
      channel.enabled &&
      channel.queries.some((query) => query.enabled && query.query_text.trim().length > 0)
  )
)

const enabledQueryCount = computed<number>(() =>
  enabledChannels.value.reduce(
    (sum, channel) =>
      sum + channel.queries.filter((query) => query.enabled && query.query_text.trim()).length,
    0
  )
)

const targetCountries = computed<string[]>(() =>
  Array.from(new Set(enabledChannels.value.flatMap((channel) => channel.target_countries)))
)

/**
 * 创建准入校验（前端即时反馈，后端仍需独立校验）：
 * Profile 启用 + 策略 active + 至少一个启用渠道 + 至少一条有效 Query
 */
const blockedReason = computed<string>(() => {
  if (!strategy.value) return ''
  if (strategy.value.profile_enabled === false) return '上游客户画像已暂停，暂不能创建新的获客任务'
  if (strategy.value.status !== 'active') return '仅启用状态的搜索策略可创建获客任务'
  if (!canActivate(strategy.value.channel_strategies)) {
    return '该策略没有可执行的渠道或有效 Query'
  }
  return ''
})

const canSubmit = computed<boolean>(() => !!strategy.value && !blockedReason.value)

async function loadStrategy(id: string): Promise<void> {
  if (!id) {
    strategy.value = null
    return
  }
  loading.value = true
  try {
    strategy.value = await fetchStrategy(id)
    if (!form.value.task_name) {
      form.value.task_name = `${strategy.value.profile_name} - ${new Date().getMonth() + 1} 月批次`
    }
  } catch {
    strategy.value = null
  } finally {
    loading.value = false
  }
}

async function bootstrap(): Promise<void> {
  form.value = { task_name: '', strategy_id: props.strategyId ?? '' }
  strategy.value = null
  formRef.value?.clearValidate()

  try {
    const result = await fetchStrategies({ page: 1, page_size: 100, status: 'active' })
    strategyOptions.value = result.list
  } catch {
    strategyOptions.value = []
  }

  if (props.strategyId) await loadStrategy(props.strategyId)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) bootstrap()
  }
)

function handleStrategyChange(value: string): void {
  loadStrategy(value)
}

function close(): void {
  emit('update:modelValue', false)
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || !strategy.value) return

  submitting.value = true
  try {
    const created = await createTask({
      task_name: form.value.task_name.trim(),
      profile_id: strategy.value.profile_id,
      strategy_id: strategy.value.id,
      // 固化创建时的策略版本，历史任务不受策略新版本影响
      strategy_version: strategy.value.version
    })
    ElMessage.success('任务已创建，待执行')
    emit('created', created.id)
    close()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="新建获客任务"
    size="720px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
    >
      <el-form-item
        label="任务名称"
        prop="task_name"
      >
        <el-input
          v-model="form.task_name"
          placeholder="例如：德国工业控制柜 - 9 月第 3 批"
          maxlength="60"
          show-word-limit
        />
      </el-form-item>

      <el-form-item
        label="搜索策略"
        prop="strategy_id"
      >
        <el-select
          v-model="form.strategy_id"
          placeholder="选择一条启用中的搜索策略"
          filterable
          :disabled="!!strategyId"
          @change="handleStrategyChange"
        >
          <el-option
            v-for="item in strategyOptions"
            :key="item.id"
            :label="`${item.profile_name}（${item.id} · v${item.version}）`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <el-skeleton
      v-if="loading"
      :rows="5"
      animated
    />

    <section
      v-else-if="strategy"
      class="task-form__preview"
    >
      <el-alert
        v-if="blockedReason"
        class="task-form__alert"
        type="error"
        :closable="false"
        show-icon
        title="当前不满足创建条件"
        :description="blockedReason"
      />

      <h4 class="task-form__preview-title">
        本次任务将固化以下策略快照
      </h4>
      <div class="task-form__grid">
        <div class="task-form__item">
          <span class="task-form__key">客户画像</span>
          <span>{{ strategy.profile_name }}</span>
        </div>
        <div class="task-form__item">
          <span class="task-form__key">搜索策略</span>
          <span>{{ strategy.id }}</span>
        </div>
        <div class="task-form__item">
          <span class="task-form__key">策略版本</span>
          <span class="num">v{{ strategy.version }}</span>
        </div>
        <div class="task-form__item">
          <span class="task-form__key">Query 数量</span>
          <span class="num">{{ enabledQueryCount }} 条</span>
        </div>
        <div class="task-form__item is-full">
          <span class="task-form__key">启用渠道</span>
          <span>
            <span
              v-for="channel in enabledChannels"
              :key="channel.channel"
              class="task-form__tag"
            >{{ labelOf(CHANNEL_OPTIONS, channel.channel) }}</span>
            <span v-if="!enabledChannels.length">-</span>
          </span>
        </div>
        <div class="task-form__item is-full">
          <span class="task-form__key">目标国家</span>
          <span>{{ labelsOf(COUNTRY_OPTIONS, targetCountries).join('、') || '-' }}</span>
        </div>
      </div>

      <p class="task-form__hint">
        创建后任务为「待执行」，需要手动点击「启动任务」才会开始执行。
      </p>
    </section>

    <template #footer>
      <div class="task-form__footer">
        <el-button @click="close">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!canSubmit"
          @click="handleSubmit"
        >
          创建任务
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.task-form__preview {
  padding: 14px 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.task-form__alert {
  margin-bottom: 12px;
}

.task-form__preview-title {
  margin: 0 0 12px;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-form__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px 20px;
}

.task-form__item {
  display: flex;
  gap: 8px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.task-form__item.is-full {
  grid-column: 1 / -1;
}

.task-form__key {
  flex: 0 0 72px;
  color: var(--color-text-secondary);
}

.task-form__tag {
  display: inline-block;
  padding: 1px 8px;
  margin: 0 6px 4px 0;
  font-size: var(--font-size-xs);
  line-height: 20px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.task-form__hint {
  margin: 12px 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.task-form__footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.task-form__preview :deep(.el-select) {
  width: 100%;
}
</style>
