/**
 * Strip speculative modulepreload hints from prerendered HTML. Nuxt emits
 * large async chunks (e.g. Mermaid) as modulepreload on the landing page,
 * which competes with mobile LCP. Chunks still load when imported.
 *
 * Important: head entries are often concatenated blobs — only remove the
 * modulepreload <link> tags, never drop the whole head entry.
 */
export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('render:html', (html) => {
    html.head = html.head.map(tag =>
      tag.replace(/<link\b[^>]*\brel="modulepreload"[^>]*>/gi, ''),
    )
  })
})
