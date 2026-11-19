export default defineNuxtConfig({
  modules: ['@nuxtjs/i18n', '@nuxt/eslint', '@nuxt/scripts', '@barzhsieh/nuxt-content-mermaid'],

  site: {
    name: 'Gefyra',
    url: 'https://gefyra.dev',
    description: 'Bridge local containers and AI coding agents into live Kubernetes clusters — instant hot-reload, zero image builds. 100% open source.',
  },

  // Docus pages use `[[lang]]` while Docus also forces i18n `strategy: 'prefix'`.
  // That yields `/en/:lang?` (landing) and `/en/:lang?/:slug(.*)*` (docs), so
  // `/en/quickstart` is stolen by landing and 404s. Strip the redundant param.
  hooks: {
    'pages:resolved': function (pages) {
      for (const page of pages) {
        if (page.path === '/:lang?' || /^\/[a-z]{2}\/:lang\?$/.test(page.path)) {
          page.path = page.path.replace(/\/:lang\?$/, '') || '/'
        }
        else if (page.path.includes('/:lang?/:slug')) {
          page.path = page.path.replace('/:lang?/:slug', '/:slug')
        }
      }
    },
  },

  devServer: {
    host: 'localhost',
    port: 3000,
  },

  contentMermaid: {
    loader: {
      init: {
        theme: 'base',
        flowchart: {
          padding: 28,
          nodeSpacing: 45,
          rankSpacing: 55,
          diagramPadding: 20,
          htmlLabels: true,
          useMaxWidth: true,
        },
        sequence: {
          diagramMarginX: 24,
          diagramMarginY: 24,
          actorMargin: 56,
          width: 170,
          height: 55,
          boxMargin: 16,
          messageMargin: 42,
          noteMargin: 14,
          useMaxWidth: true,
        },
        themeVariables: {
          fontSize: '14px',
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
    domain: 'https://gefyra.dev',
    title: 'Gefyra — Kubernetes Local Development',
    description: 'Docs for Gefyra: bridge local Docker/Podman containers and AI coding agents into live Kubernetes clusters with instant hot-reload. No image builds, no CI waiting loops.',
    full: {
      title: 'Gefyra Documentation',
      description: 'Complete Gefyra documentation: quickstart, AI agent workflows, developer bridges, shared staging clusters, cloud guides (GKE, EKS), architecture, and CLI reference.',
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
