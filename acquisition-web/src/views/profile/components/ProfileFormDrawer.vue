<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  APPLICATION_SCENARIO_OPTIONS,
  COMPANY_SIZE_OPTIONS,
  COMPANY_TYPE_OPTIONS,
  COUNTRY_OPTIONS,
  INDUSTRY_OPTIONS,
  PRIORITY_OPTIONS,
  PRODUCT_LINE_OPTIONS,
  REGION_OPTIONS,
  TARGET_ROLE_OPTIONS
} from '@/mock/dict'
import { createProfile, updateProfile } from '@/api/profile'
import type { CustomerProfile, ProfilePayload } from '@/types/profile'

const props = defineProps<{
  modelValue: boolean
  /** 有值为编辑，无值为新建 */
  profile: CustomerProfile | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved'): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

function emptyForm(): ProfilePayload {
  return {
    profile_name: '',
    target_industries: [],
    target_regions: [],
    target_countries: [],
    company_types: [],
    company_size: 'any',
    product_lines: [],
    application_scenarios: [],
    required_signals: [''],
    exclude_signals: [''],
    target_roles: [],
    daily_quota: 30,
    priority: 'medium',
    is_enabled: true
  }
}

const form = reactive<ProfilePayload>(emptyForm())

const isEdit = computed<boolean>(() => !!props.profile)
const title = computed<string>(() => (isEdit.value ? '编辑客户画像' : '新建客户画像'))

const rules: FormRules = {
  profile_name: [
    { required: true, message: '请输入画像名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  target_industries: [
    { required: true, type: 'array', min: 1, message: '至少选择一个目标行业', trigger: 'change' }
  ],
  target_countries: [
    { required: true, type: 'array', min: 1, message: '至少选择一个目标国家', trigger: 'change' }
  ],
  product_lines: [
    { required: true, type: 'array', min: 1, message: '至少选择一条匹配产品线', trigger: 'change' }
  ],
  daily_quota: [{ required: true, message: '请输入每日发现配额', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
}

/** 打开时装载数据：编辑回填，新建重置 */
watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    const source = props.profile
    Object.assign(form, source ? structuredClone(toPayload(source)) : emptyForm())
    if (!form.required_signals.length) form.required_signals = ['']
    if (!form.exclude_signals.length) form.exclude_signals = ['']
    formRef.value?.clearValidate()
  }
)

/** 实体 → 提交体：剥离后端生成的 id 与时间戳 */
function toPayload(profile: CustomerProfile): ProfilePayload {
  return {
    profile_name: profile.profile_name,
    target_industries: profile.target_industries,
    target_regions: profile.target_regions,
    target_countries: profile.target_countries,
    company_types: profile.company_types,
    company_size: profile.company_size,
    product_lines: profile.product_lines,
    application_scenarios: profile.application_scenarios,
    required_signals: profile.required_signals,
    exclude_signals: profile.exclude_signals,
    target_roles: profile.target_roles,
    daily_quota: profile.daily_quota,
    priority: profile.priority,
    is_enabled: profile.is_enabled
  }
}

function addSignal(field: 'required_signals' | 'exclude_signals'): void {
  form[field].push('')
}

function removeSignal(field: 'required_signals' | 'exclude_signals', index: number): void {
  form[field].splice(index, 1)
  if (!form[field].length) form[field].push('')
}

function close(): void {
  emit('update:modelValue', false)
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 动态条件行过滤空值后提交
  const payload: ProfilePayload = {
    ...form,
    required_signals: form.required_signals.map((item) => item.trim()).filter(Boolean),
    exclude_signals: form.exclude_signals.map((item) => item.trim()).filter(Boolean)
  }

  submitting.value = true
  try {
    if (props.profile) {
      await updateProfile(props.profile.id, payload)
      ElMessage.success('画像已更新')
    } else {
      await createProfile(payload)
      ElMessage.success('画像已创建')
    }
    emit('saved')
    close()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="720px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="profile-form"
    >
      <!-- 基本信息 -->
      <section class="profile-form__group">
        <h4 class="profile-form__group-title">
          基本信息
        </h4>
        <el-form-item
          label="画像名称"
          prop="profile_name"
        >
          <el-input
            v-model="form.profile_name"
            placeholder="例如：德国工业控制柜连接器采购商"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <div class="profile-form__row">
          <el-form-item
            label="目标行业"
            prop="target_industries"
          >
            <el-select
              v-model="form.target_industries"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择目标行业"
            >
              <el-option
                v-for="item in INDUSTRY_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标地区">
            <el-select
              v-model="form.target_regions"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择目标地区"
            >
              <el-option
                v-for="item in REGION_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item
          label="目标国家"
          prop="target_countries"
        >
          <el-select
            v-model="form.target_countries"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择目标国家"
          >
            <el-option
              v-for="item in COUNTRY_OPTIONS"
              :key="item.value"
              :label="`${item.label}（${item.value}）`"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </section>

      <!-- 企业特征 -->
      <section class="profile-form__group">
        <h4 class="profile-form__group-title">
          企业特征
        </h4>
        <div class="profile-form__row">
          <el-form-item label="企业类型">
            <el-select
              v-model="form.company_types"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择企业类型"
            >
              <el-option
                v-for="item in COMPANY_TYPE_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="企业规模">
            <el-select
              v-model="form.company_size"
              placeholder="请选择企业规模"
            >
              <el-option
                v-for="item in COMPANY_SIZE_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
      </section>

      <!-- 产品需求 -->
      <section class="profile-form__group">
        <h4 class="profile-form__group-title">
          产品需求
        </h4>
        <el-form-item
          label="匹配产品线"
          prop="product_lines"
        >
          <el-select
            v-model="form.product_lines"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择匹配产品线"
          >
            <el-option
              v-for="item in PRODUCT_LINE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标应用场景">
          <el-select
            v-model="form.application_scenarios"
            multiple
            filterable
            placeholder="请选择目标应用场景"
          >
            <el-option
              v-for="item in APPLICATION_SCENARIO_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </section>

      <!-- AI 判断条件：轻量使用 AI 紫作为辅助色 -->
      <section class="profile-form__group is-ai">
        <h4 class="profile-form__group-title">
          AI 判断条件
          <span class="profile-form__ai-tag">AI</span>
        </h4>
        <p class="profile-form__group-hint">
          这些条件会作为 AI 判断企业是否相关（is_relevant）的依据。
        </p>

        <el-form-item label="必须满足条件">
          <div class="profile-form__signals">
            <div
              v-for="(item, index) in form.required_signals"
              :key="`required-${index}`"
              class="profile-form__signal"
            >
              <el-input
                v-model="form.required_signals[index]"
                placeholder="例如：官网明确展示工业控制柜产品"
                maxlength="100"
              />
              <el-button
                text
                :disabled="form.required_signals.length === 1 && !item"
                @click="removeSignal('required_signals', index)"
              >
                删除
              </el-button>
            </div>
            <el-button
              text
              type="primary"
              @click="addSignal('required_signals')"
            >
              + 添加判断条件
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="排除条件">
          <div class="profile-form__signals">
            <div
              v-for="(item, index) in form.exclude_signals"
              :key="`exclude-${index}`"
              class="profile-form__signal"
            >
              <el-input
                v-model="form.exclude_signals[index]"
                placeholder="例如：纯电商零售网站"
                maxlength="100"
              />
              <el-button
                text
                :disabled="form.exclude_signals.length === 1 && !item"
                @click="removeSignal('exclude_signals', index)"
              >
                删除
              </el-button>
            </div>
            <el-button
              text
              type="primary"
              @click="addSignal('exclude_signals')"
            >
              + 添加排除条件
            </el-button>
          </div>
        </el-form-item>
      </section>

      <!-- 联系人 -->
      <section class="profile-form__group">
        <h4 class="profile-form__group-title">
          联系人
        </h4>
        <el-form-item label="目标联系人角色">
          <el-select
            v-model="form.target_roles"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择目标联系人角色"
          >
            <el-option
              v-for="item in TARGET_ROLE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </section>

      <!-- 调度 -->
      <section class="profile-form__group">
        <h4 class="profile-form__group-title">
          调度
        </h4>
        <div class="profile-form__row">
          <el-form-item
            label="每日发现配额"
            prop="daily_quota"
          >
            <el-input-number
              v-model="form.daily_quota"
              :min="1"
              :max="1000"
              :step="5"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item
            label="优先级"
            prop="priority"
          >
            <el-select
              v-model="form.priority"
              placeholder="请选择优先级"
            >
              <el-option
                v-for="item in PRIORITY_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="启用状态">
          <el-switch
            v-model="form.is_enabled"
            active-text="启用"
            inactive-text="暂停"
          />
        </el-form-item>
      </section>
    </el-form>

    <template #footer>
      <div class="profile-form__footer">
        <el-button @click="close">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ isEdit ? '保存修改' : '创建画像' }}
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.profile-form__group {
  padding: 16px 18px;
  margin-bottom: 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

/* AI 判断条件区：轻量 AI 紫辅助色，不大面积使用 */
.profile-form__group.is-ai {
  background: var(--color-ai-bg);
  border-color: var(--color-ai-border);
}

.profile-form__group-title {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 12px;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.profile-form__ai-tag {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-card);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

.profile-form__group-hint {
  margin: -6px 0 12px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.profile-form__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0 16px;
}

.profile-form__signals {
  width: 100%;
}

.profile-form__signal {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.profile-form__footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.profile-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.profile-form :deep(.el-select),
.profile-form :deep(.el-input-number) {
  width: 100%;
}
</style>
