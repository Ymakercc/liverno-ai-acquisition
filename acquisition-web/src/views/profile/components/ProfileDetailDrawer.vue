<script setup lang="ts">
import {
  APPLICATION_SCENARIO_OPTIONS,
  COMPANY_SIZE_OPTIONS,
  COMPANY_TYPE_OPTIONS,
  COUNTRY_OPTIONS,
  INDUSTRY_OPTIONS,
  PRIORITY_OPTIONS,
  PRODUCT_LINE_OPTIONS,
  REGION_OPTIONS,
  TARGET_ROLE_OPTIONS,
  labelOf,
  labelsOf
} from '@/mock/dict'
import type { CustomerProfile } from '@/types/profile'

defineProps<{
  modelValue: boolean
  profile: CustomerProfile | null
}>()

const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void }>()
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="画像详情"
    size="720px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div
      v-if="profile"
      class="profile-detail"
    >
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item
          label="画像名称"
          :span="2"
        >
          {{ profile.profile_name }}
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          {{ labelOf(PRIORITY_OPTIONS, profile.priority) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            :type="profile.is_enabled ? 'success' : 'info'"
            size="small"
            effect="light"
          >
            {{ profile.is_enabled ? '启用' : '暂停' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="每日发现配额">
          {{ profile.daily_quota }}
        </el-descriptions-item>
        <el-descriptions-item label="企业规模">
          {{ labelOf(COMPANY_SIZE_OPTIONS, profile.company_size) }}
        </el-descriptions-item>
        <el-descriptions-item
          label="目标行业"
          :span="2"
        >
          <el-tag
            v-for="item in labelsOf(INDUSTRY_OPTIONS, profile.target_industries)"
            :key="item"
            class="profile-detail__tag"
            size="small"
            effect="plain"
          >
            {{ item }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item
          label="目标地区"
          :span="2"
        >
          {{ labelsOf(REGION_OPTIONS, profile.target_regions).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item
          label="目标国家"
          :span="2"
        >
          <el-tag
            v-for="(item, index) in profile.target_countries"
            :key="item"
            class="profile-detail__tag"
            size="small"
            effect="plain"
          >
            {{ labelsOf(COUNTRY_OPTIONS, profile.target_countries)[index] }}（{{ item }}）
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item
          label="企业类型"
          :span="2"
        >
          {{ labelsOf(COMPANY_TYPE_OPTIONS, profile.company_types).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item
          label="匹配产品线"
          :span="2"
        >
          {{ labelsOf(PRODUCT_LINE_OPTIONS, profile.product_lines).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item
          label="目标应用场景"
          :span="2"
        >
          <el-tag
            v-for="item in labelsOf(APPLICATION_SCENARIO_OPTIONS, profile.application_scenarios)"
            :key="item"
            class="profile-detail__tag"
            size="small"
            effect="plain"
          >
            {{ item }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item
          label="目标联系人角色"
          :span="2"
        >
          {{ labelsOf(TARGET_ROLE_OPTIONS, profile.target_roles).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ profile.created_at }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ profile.updated_at }}
        </el-descriptions-item>
      </el-descriptions>

      <section class="profile-detail__ai">
        <h4 class="profile-detail__ai-title">
          AI 判断条件
          <span class="profile-detail__ai-tag">AI</span>
        </h4>
        <div class="profile-detail__signals">
          <div class="profile-detail__signal-label">
            必须满足
          </div>
          <ul
            v-if="profile.required_signals.length"
            class="profile-detail__list"
          >
            <li
              v-for="item in profile.required_signals"
              :key="item"
            >
              {{ item }}
            </li>
          </ul>
          <span
            v-else
            class="profile-detail__empty"
          >未设置</span>
        </div>
        <div class="profile-detail__signals">
          <div class="profile-detail__signal-label">
            排除条件
          </div>
          <ul
            v-if="profile.exclude_signals.length"
            class="profile-detail__list"
          >
            <li
              v-for="item in profile.exclude_signals"
              :key="item"
            >
              {{ item }}
            </li>
          </ul>
          <span
            v-else
            class="profile-detail__empty"
          >未设置</span>
        </div>
      </section>
    </div>
  </el-drawer>
</template>

<style scoped>
.profile-detail__tag {
  margin: 2px 6px 2px 0;
}

.profile-detail__ai {
  padding: 16px 18px;
  margin-top: 16px;
  background: var(--color-ai-bg);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-card);
}

.profile-detail__ai-title {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 12px;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.profile-detail__ai-tag {
  padding: 0 5px;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--color-ai-text);
  background: var(--color-card);
  border: 1px solid var(--color-ai-border);
  border-radius: var(--radius-sm);
}

.profile-detail__signals + .profile-detail__signals {
  margin-top: 12px;
}

.profile-detail__signal-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.profile-detail__list {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.profile-detail__list li {
  margin-bottom: 4px;
}

.profile-detail__empty {
  font-size: var(--font-size-sm);
  color: var(--color-text-placeholder);
}
</style>
