export default defineNuxtConfig({
  modules: ['@nuxtjs/i18n', '@nuxt/eslint'],
  css: ['~/assets/scss/main.scss'],
  eslint: {
    config: {
      standalone: false,
    },
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
  icon: {
    provider: 'iconify',
    customCollections: [{
      prefix: 'gefyra',
      dir: './assets/icons',
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
