# Gefyra Documentation

Source for [gefyra.dev](https://gefyra.dev) — the official documentation for [Gefyra](https://github.com/gefyrahq/gefyra), the tool for blazingly-fast, rock-solid local application development with Kubernetes.

Run local code in any cluster without the build-and-push cycle. Overlay containers, debug against real dependencies, and ship with confidence.

## Live site

**https://gefyra.dev**

Changes on `main` are built and published to GitHub Pages via [`.github/workflows/docs.yaml`](../.github/workflows/docs.yaml).

## Local development

```bash
cd gefyra-docs
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). English is the default locale; routes use the `/en/...` prefix (with `/` redirecting to the English home page in production).

### Other scripts

| Command | Description |
| --- | --- |
| `npm run build` | Production build (SSR) |
| `npm run generate` | Static export for GitHub Pages |
| `npm run docs:cli` | Regenerate CLI reference from the Python client |
| `npm run lint` | ESLint |
| `npm run lint:fix` | ESLint with auto-fix |

## Content

Markdown lives under `content/en/`, grouped by topic:

| Section | Topics |
| --- | --- |
| `1.quick-start/` | Introduction, installation, first steps, Docker Desktop extension, CLI reference |
| `2.local-environments/` | Colima, Docker Desktop, k3d, kind, minikube |
| `3.shared-environments/` | Multi-user setups, clients, connecting |
| `4.remote-k8s/` | GCP, EKS, SYS11 |
| `5.usecases-and-demos/` | Tutorials and walkthroughs |
| `6.technical-details/` | Architecture, concepts |
| `7.information/` | Run vs bridge, v1 vs v2, media, about |

Navigation order and sidebar labels come from `.navigation.yml` files in each folder. Pages support [Docus MDC](https://docus.dev) (Vue components in Markdown, e.g. `::card`, `::tabs`).

### CLI reference (generated)

`content/en/1.quick-start/5.cli.md` is **not** hand-edited. It is produced from the Gefyra CLI:

```bash
npm run docs:cli
```

That runs `gefyra-docs` in the `client` package (Poetry). CI does the same before each docs deploy.

## Customization

| Path | Purpose |
| --- | --- |
| `app/` | App config, SCSS, Vue components, custom icons (`app/assets/icons`) |
| `public/` | Static assets (favicon, images) |
| `nuxt.config.ts` | i18n, prerender, Mermaid, content highlighters, LLM hints |

Site metadata (colors, social links) is in `app/app.config.ts`.

## Stack

Built on [Docus](https://docus.dev) (Nuxt documentation layer):

- [Nuxt 4](https://nuxt.com) + [Nuxt Content](https://content.nuxt.com/)
- [@nuxtjs/i18n](https://i18n.nuxt.com/) (English only today)
- [Nuxt UI](https://ui.nuxt.com/) via Docus
- [Mermaid](https://mermaid.js.org/) via `@barzhsieh/nuxt-content-mermaid`
- Tailwind CSS 4

For Docus-specific authoring patterns, see the [Docus documentation](https://docus.dev).

## Contributing

1. Edit or add Markdown under `content/en/`.
2. Run `npm run dev` and check the page in the browser.
3. Open a PR against the main [gefyra](https://github.com/gefyrahq/gefyra) repository.

Questions and feedback: [GitHub Issues](https://github.com/gefyrahq/gefyra/issues) · [Discord](https://discord.gg/8NTPMVPaKy)

## License

Same license as the [Gefyra](https://github.com/gefyrahq/gefyra) project (MIT).
