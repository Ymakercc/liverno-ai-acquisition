<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found app-card">
    <div class="not-found__code">
      404
    </div>
    <p class="not-found__text">
      页面不存在，请检查地址是否正确。
    </p>
    <el-button
      type="primary"
      @click="router.push('/dashboard')"
    >
      返回工作台
    </el-button>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
}

.not-found__code {
  font-size: 56px;
  font-weight: 700;
  color: var(--color-primary);
}

.not-found__text {
  margin: 0;
  color: var(--color-text-secondary);
}
</style>
