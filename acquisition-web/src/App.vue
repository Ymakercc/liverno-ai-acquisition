<script setup lang="ts">
/**
 * 全局中文语言包
 * 覆盖分页、表格空态、下拉无数据等组件内置文案，
 * 命令式服务组件（MessageBox 等）的按钮文案在调用处显式指定，
 * 使用具体动作名而非泛化的「确认」。
 */
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<template>
  <el-config-provider :locale="zhCn">
    <RouterView />
  </el-config-provider>
</template>
