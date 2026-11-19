<script setup lang="ts">
defineProps<{
  code: string
}>()
</script>

<template>
  <Mermaid :code="code" />
</template>
