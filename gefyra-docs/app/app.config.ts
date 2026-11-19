export default defineAppConfig({
  ui: {
    colors: {
      primary: 'yellow',
      secondary: 'slate',
    },
  },
  seo: {
    // Avoid package.json name ("gefyra-docs") leaking into <title> / og:site_name
    titleTemplate: '%s · Gefyra',
    title: 'Gefyra — Kubernetes Local Development',
    description: 'Bridge local containers and AI coding agents into live Kubernetes clusters — instant hot-reload, zero image builds. 100% open source.',
    schema: {
      type: 'SoftwareApplication',
      applicationCategory: 'DeveloperApplication',
      operatingSystem: 'Linux, macOS, Windows',
      price: 0,
      priceCurrency: 'USD',
      sameAs: [
        'https://github.com/gefyrahq/gefyra',
        'https://discord.gg/8NTPMVPaKy',
        'https://x.com/BLUESHOE_GmbH',
      ],
      organization: {
        name: 'Blueshoe',
        url: 'https://blueshoe.io',
        logo: 'https://gefyra.dev/brand/blueshoe-logo-horizontal.png',
        sameAs: [
          'https://github.com/blueshoe',
          'https://www.linkedin.com/company/blueshoe',
          'https://x.com/BLUESHOE_GmbH',
        ],
      },
    },
  },
  header: {
    title: 'Gefyra',
  },
  socials: {
    github: 'https://github.com/gefyrahq/gefyra',
    x: 'https://x.com/BLUESHOE_GmbH',
    discord: 'https://discord.gg/8NTPMVPaKy',
  },
})
