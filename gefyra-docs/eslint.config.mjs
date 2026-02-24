// @ts-check
import antfu from '@antfu/eslint-config'
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  antfu({
    vue: true,
    formatters: {
      css: true,
    },
    rules: {
      'no-console': 'warn',
    },
    ignores: [
      'content/**',
    ],
  }),
)
