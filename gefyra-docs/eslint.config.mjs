import antfu from '@antfu/eslint-config'
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  antfu({
    vue: true,
    formatters: {
      markdown: false,
      css: true,
    },
    rules: {
      'no-console': 'warn',
      'vue/max-attributes-per-line': 'warn',
      'vue/require-default-prop': 'warn',
    },
  }),
)
