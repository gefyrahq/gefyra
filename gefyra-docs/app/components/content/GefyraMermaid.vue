<script setup lang="ts">
const colorMode = useColorMode()
const { $mermaid } = useNuxtApp()
const mermaidContainer = ref<HTMLDivElement | null>(null)
const hasRenderedOnce = ref(false) // Track the initial render
let mermaidDefinition = ''
let observer: IntersectionObserver | null = null

const mermaidTheme = computed(() => {
  return colorMode.value === 'dark' ? 'dark' : 'default'
})

async function renderMermaid() {
  if (!mermaidContainer.value || !mermaidDefinition)
    return

  try {
    mermaidContainer.value.removeAttribute('data-processed')
    mermaidContainer.value.textContent = mermaidDefinition
    await nextTick()

    $mermaid().initialize({ startOnLoad: false, theme: mermaidTheme.value })
    await $mermaid().run({
      nodes: [mermaidContainer.value],
    })
    hasRenderedOnce.value = true // Mark as rendered
  }
  catch (e) {
    console.error('Error running Mermaid:', e)
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = '⚠️ Mermaid Chart Syntax Error'
    }
  }
}

onMounted(() => {
  if (mermaidContainer.value) {
    mermaidDefinition = mermaidContainer.value.textContent?.trim() ?? ''

    observer = new IntersectionObserver(
      (entries) => {
        // If the element is visible and we haven't rendered it yet
        if (entries[0]?.isIntersecting && !hasRenderedOnce.value) {
          renderMermaid()

          // Disconnect the observer after the first successful render
          if (observer) {
            observer.disconnect()
          }
        }
      },
      { threshold: 0.1 },
    )

    observer.observe(mermaidContainer.value)
  }
})

// Clean up the observer when the component is unmounted
onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
})

// Watch for theme changes and re-render only if it's already been rendered once
watch(mermaidTheme, () => {
  if (hasRenderedOnce.value) {
    renderMermaid()
  }
})
</script>

<template>
  <div ref="mermaidContainer" class="mermaid">
    <slot />
  </div>
</template>

<style>
.mermaid:not([data-processed]) {
  color: transparent;
  min-height: 10px; /* Give it a minimum height so the observer can see it */
}
.mermaid {
  display: flex;
  justify-content: center;
}
</style>
