<script setup lang="ts">
import { CHANNEL_OPTIONS, COUNTRY_OPTIONS, STRATEGY_STATUS_OPTIONS, labelOf, labelsOf } from '@/mock/dict'
import type { SearchStrategy } from '@/types/strategy'

defineProps<{
  modelValue: boolean
  strategy: SearchStrategy | null
}>()

const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void }>()
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="策略详情"
    size="820px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div
      v-if="strategy"
      class="strategy-detail"
    >
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item
          label="来源画像"
          :span="2"
        >
          {{ strategy.profile_name }}
        </el-descriptions-item>
        <el-descriptions-item label="策略编号">
          {{ strategy.id }}
        </el-descriptions-item>
        <el-descriptions-item label="版本">
          v{{ strategy.version }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ labelOf(STRATEGY_STATUS_OPTIONS, strategy.status) }}
        </el-descriptions-item>
        <el-descriptions-item label="覆盖渠道">
          {{ strategy.channel_strategies.map((item) => labelOf(CHANNEL_OPTIONS, item.channel)).join('、') }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ strategy.created_at }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ strategy.updated_at }}
        </el-descriptions-item>
      </el-descriptions>

      <section
        v-for="channel in strategy.channel_strategies"
        :key="channel.channel"
        class="detail-channel"
        :class="{ 'is-off': !channel.enabled }"
      >
        <header class="detail-channel__head">
          <span class="detail-channel__name">{{ labelOf(CHANNEL_OPTIONS, channel.channel) }}</span>
          <span class="detail-channel__status">{{ channel.enabled ? '启用' : '停用' }}</span>
          <span class="detail-channel__countries">
            {{ labelsOf(COUNTRY_OPTIONS, channel.target_countries).join('、') }}
          </span>
        </header>

        <p
          v-if="channel.strategy_summary"
          class="detail-channel__summary"
        >
          {{ channel.strategy_summary }}
        </p>

        <ul class="detail-channel__queries">
          <li
            v-for="query in channel.queries"
            :key="query.id"
            class="detail-query"
            :class="{ 'is-off': !query.enabled }"
          >
            <span class="detail-query__text">{{ query.query_text }}</span>
            <span class="detail-query__meta">
              {{ query.country_code ? labelOf(COUNTRY_OPTIONS, query.country_code) : '不限' }}
              · {{ query.language || 'en' }}
              · {{ query.enabled ? '启用' : '停用' }}
            </span>
          </li>
        </ul>
      </section>
    </div>
  </el-drawer>
</template>

<style scoped>
.detail-channel {
  padding: 14px 16px;
  margin-top: 14px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.detail-channel.is-off {
  background: var(--color-bg);
}

.detail-channel__head {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.detail-channel__name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.detail-channel__status,
.detail-channel__countries {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.detail-channel__summary {
  margin: 8px 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.detail-channel__queries {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.detail-query {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
  padding: 7px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.detail-query:last-child {
  border-bottom: none;
}

.detail-query.is-off .detail-query__text {
  color: var(--color-text-placeholder);
  text-decoration: line-through;
}

.detail-query__text {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  word-break: break-all;
}

.detail-query__meta {
  flex: 0 0 auto;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}
</style>
