<script setup lang="ts">
defineProps<{
  title: string
  tag: string
  logo?: string
  url: string
  linkText?: string
}>()
</script>

<template>
  <a
    :href="url"
    target="_blank"
    rel="noopener noreferrer"
    class="ecosystem-card"
  >
    <div class="ecosystem-card-header">
      <img
        v-if="logo"
        :src="logo"
        :alt="title"
        class="ecosystem-logo"
      >
      <span class="ecosystem-tag">{{ tag }}</span>
    </div>
    <h3 class="ecosystem-title">{{ title }}</h3>
    <div class="ecosystem-body">
      <slot />
    </div>
    <div class="ecosystem-footer">
      <span class="ecosystem-link">{{ linkText || 'Explore →' }}</span>
    </div>
  </a>
</template>
