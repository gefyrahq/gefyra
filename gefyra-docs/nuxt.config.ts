export default defineNuxtConfig({
  modules: ['@nuxtjs/i18n', '@nuxt/eslint', '@nuxt/scripts', '@barzhsieh/nuxt-content-mermaid'],

  devServer: {
    host: 'localhost',
    port: 3000,
  },

  contentMermaid: {
    loader: {
      init: {
        theme: 'base',
        themeVariables: {
          fontSize: '16px',
          primaryColor: '#f6bc00',
          primaryTextColor: '#1d2a2f',
          primaryBorderColor: '#bb6b02',
          lineColor: '#f6bc00',
          secondaryColor: '#2d3b41',
          tertiaryColor: '#1d2a2f',
          background: 'transparent',
          mainBkg: '#2d3b41',
          nodeBorder: '#f6bc00',
          clusterBkg: '#1d2a2f',
          clusterBorder: '#50808a',
          titleColor: '#f6bc00',
          edgeLabelBackground: '#2d3b41',
          actorBkg: '#2d3b41',
          actorBorder: '#f6bc00',
          actorTextColor: '#f9fafb',
          actorLineColor: '#50808a',
          signalColor: '#f6bc00',
          signalTextColor: '#f9fafb',
          labelBoxBkgColor: '#2d3b41',
          labelBoxBorderColor: '#f6bc00',
          labelTextColor: '#f9fafb',
          loopTextColor: '#f6bc00',
          noteBkgColor: '#f6bc00',
          noteTextColor: '#1d2a2f',
          noteBorderColor: '#e29700',
        },
      },
    },
    toolbar: {
      buttons: {
        copy: false,
        fullscreen: false,
        expand: false,
      },
    },
    expand: false,
  },

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

  $development: {
    vite: {
      optimizeDeps: {
        include: [
          '@vue/devtools-core',
          '@vue/devtools-kit',
        ],
      },
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
