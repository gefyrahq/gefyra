export default defineNuxtConfig({
  modules: [
    '@nuxtjs/i18n',
    '@nuxt/eslint',
    '@nuxt/fonts',
    '@nuxt/icon',
    '@nuxt/image',
    '@nuxt/ui-pro',
  ],
  css: ['~/assets/scss/main.scss'],
  eslint: {
    config: {
      standalone: false,
    },
  },
  icon: {
    provider: 'server',
    customCollections: [{
      prefix: 'gefyra',
      dir: './assets/icons',
    }],
  },
  i18n: {
    defaultLocale: 'en',
    locales: [{
      code: 'en',
      name: 'English',
    }, {
      code: 'fr',
      name: 'Français',
    }],
  },
  llms: {
    domain: 'https://gefyra.dev/',
    title: 'Gefyra Documentation',
    description: 'Gefyra - Kubernetes Development Environment',
    full: {
      title: 'Gefyra Documentation',
      description: 'Gefyra - Kubernetes Development Environment',
    },
  },
})
