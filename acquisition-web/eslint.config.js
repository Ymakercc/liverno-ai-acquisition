import js from '@eslint/js'
import globals from 'globals'
import ts from 'typescript-eslint'
import vue from 'eslint-plugin-vue'

export default ts.config(
  {
    ignores: ['dist/**', 'node_modules/**', 'auto-imports.d.ts', 'components.d.ts']
  },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: ts.parser }
    }
  },
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        // Element Plus 命令式服务组件由 unplugin-auto-import 注入
        ElMessage: 'readonly',
        ElMessageBox: 'readonly',
        ElNotification: 'readonly',
        ElLoading: 'readonly'
      }
    },
    rules: {
      // 页面统一为 index.vue / detail.vue，组件名由目录表达
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-explicit-any': 'error'
    }
  }
)
