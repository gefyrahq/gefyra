<script setup lang="ts">
useHead({
  link: [
    {
      rel: 'preload',
      as: 'image',
      href: '/img/stage-texture.svg',
      fetchpriority: 'high',
    },
  ],
})
</script>

<template>
  <UIcon
    name="i-gefyra-logo-vertical"
    mode="svg"
    class="home-icon"
    aria-label="Gefyra"
  />
</template>
