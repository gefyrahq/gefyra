<script setup lang="ts">
import type { Component } from 'vue'

const props = defineProps<{
  code: string
}>()

const root = ref<HTMLElement | null>(null)
const visible = ref(false)
const MermaidComp = shallowRef<Component | null>(null)
const encodedCode = computed(() => encodeURIComponent(props.code))

async function loadMermaid() {
  if (MermaidComp.value) {
    return
  }
  // Local island keeps Mermaid out of the landing-page modulepreload graph.
  const mod = await import('./MermaidIsland.vue')
  MermaidComp.value = mod.default
}

onMounted(() => {
  const el = root.value
  if (!el || import.meta.server) {
    return
  }

  const reveal = () => {
    visible.value = true
    void loadMermaid()
  }

  if (!('IntersectionObserver' in window)) {
    reveal()
    return
  }

  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some(entry => entry.isIntersecting)) {
        reveal()
        observer.disconnect()
      }
    },
    { rootMargin: '240px 0px' },
  )

  observer.observe(el)
  onBeforeUnmount(() => observer.disconnect())
})
</script>

<template>
  <div
    ref="root"
    class="deferred-mermaid"
  >
    <ClientOnly>
      <component
        :is="MermaidComp"
        v-if="visible && MermaidComp"
        :code="encodedCode"
      />
      <template #fallback>
        <div
          class="deferred-mermaid-placeholder"
          aria-hidden="true"
        />
      </template>
    </ClientOnly>
    <div
      v-if="!(visible && MermaidComp)"
      class="deferred-mermaid-placeholder"
      aria-hidden="true"
    />
  </div>
</template>
