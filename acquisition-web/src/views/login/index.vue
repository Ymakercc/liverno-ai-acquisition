<script setup lang="ts">
/** 登录页占位：本阶段不实现认证逻辑与接口（CLAUDE.md 第 11 章） */
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="login">
    <div class="login__card app-card">
      <div class="login__brand">
        <div class="login__logo">
          K
        </div>
        <div>
          <div class="login__name">
            KULON ELECTRONICS
          </div>
          <div class="login__sub">
            AI 自动获客系统
          </div>
        </div>
      </div>
      <p class="login__desc">
        登录页：账号登录并获取角色与菜单权限。当前阶段仅为占位，未接入认证接口。
      </p>
      <el-button
        type="primary"
        class="login__btn"
        @click="router.push('/dashboard')"
      >
        进入系统
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--color-bg);
}

.login__card {
  width: 380px;
  padding: 32px;
}

.login__brand {
  display: flex;
  gap: 12px;
  align-items: center;
}

.login__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-inverse);
  background: var(--color-primary);
  border-radius: var(--radius-base);
}

.login__name {
  font-size: var(--font-size-base);
  font-weight: 600;
}

.login__sub {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.login__desc {
  margin: 24px 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.login__btn {
  width: 100%;
}
</style>
