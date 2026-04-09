export default defineNuxtConfig({
  modules: ['@nuxtjs/i18n', '@nuxt/eslint', '@nuxt/scripts', '@barzhsieh/nuxt-content-mermaid'],

  css: ['~/assets/scss/main.scss'],

  app: {
    head: {
      script: [
        {
          'data-collect-dnt': true,
          'async': true,
          'src': 'https://scripts.simpleanalyticscdn.com/latest.js',
        },
      ],
    },
  },

  eslint: {
    config: {
      standalone: false,
    },
  },
  ssr: true, // Enable server-side rendering for pre-rendering

  nitro: {
    prerender: {
      // Crawl all linked pages
      crawlLinks: true,
      // Explicitly add routes
      routes: ['/sitemap.xml', '/robots.txt'],
      // autoSubfolderIndex: true,
    },
    preset: 'github_pages',
  },

  i18n: {
    defaultLocale: 'en',
    baseUrl: 'https://gefyra.dev',
    strategy: 'prefix_except_default',
    locales: [{
      code: 'en',
      name: 'English',
    }],
  },

  fonts: {
    provider: 'google',
  },

  icon: {
    provider: 'server',
    customCollections: [{
      prefix: 'gefyra',
      dir: './app/assets/icons',
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

  content: {
    build: {
      markdown: {
        highlight: {
          langs: ['js', 'jsx', 'json', 'ts', 'tsx', 'vue', 'css', 'html', 'vue', 'bash', 'md', 'mdc', 'yaml', 'dockerfile', 'py', 'mermaid', 'diff'],
        },
      },
    },
  },
})
