<script setup lang="ts">
const { $mermaid } = useNuxtApp()
const mermaidContainer = ref<HTMLDivElement | null>(null)

onMounted(async () => {
  if (mermaidContainer.value) {
    const definition = mermaidContainer.value.textContent?.trim() ?? ''
    if (definition) {
      mermaidContainer.value.textContent = definition
      await nextTick()
      try {
        $mermaid().initialize({ startOnLoad: false, theme: 'default' })
        await $mermaid().run({
          nodes: [mermaidContainer.value],
        })
      }
      catch (e) {
        console.error('Error running Mermaid:', e)
        mermaidContainer.value.innerHTML = '⚠️ Mermaid Chart Syntax Error'
      }
    }
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
}
</style>
