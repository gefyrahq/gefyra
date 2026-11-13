<script setup lang="ts">
const route = useRoute()

const navLinks = [
  {
    label: 'Quickstart',
    to: '/en/quickstart/',
    prefix: '/quickstart',
    icon: 'i-lucide-rocket',
  },
  {
    label: 'AI Agents',
    to: '/en/ai-agents/cluster-ground-truth',
    prefix: '/ai-agents',
    icon: 'i-lucide-bot',
  },
  {
    label: 'Workflows',
    to: '/en/developer-workflows/hot-reloading',
    prefix: '/developer-workflows',
    icon: 'i-lucide-laptop',
  },
  {
    label: 'Guides',
    to: '/en/cluster-guides/overview',
    prefix: '/cluster-guides',
    icon: 'i-lucide-network',
  },
  {
    label: 'CLI Reference',
    to: '/en/reference/cli',
    prefix: '/reference/cli',
    icon: 'i-lucide-square-terminal',
  },
]

function isLinkActive(prefix: string) {
  return route.path.includes(prefix)
}
</script>

<template>
  <nav class="hidden lg:flex items-center justify-center gap-1 xl:gap-2">
    <NuxtLink
      v-for="item in navLinks"
      :key="item.to"
      :to="item.to"
      class="nav-shortcut-link"
      :class="{ 'is-active': isLinkActive(item.prefix) }"
    >
      <UIcon
        :name="item.icon"
        class="size-4 shrink-0 transition-transform group-hover:scale-110"
      />
      <span>{{ item.label }}</span>
    </NuxtLink>
  </nav>
</template>

<style scoped lang="scss">
.nav-shortcut-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.65rem;
  border-radius: 0.5rem;
  font-size: 0.84rem;
  font-weight: 500;
  color: #4b5563;
  text-decoration: none;
  transition: all 0.15s ease;
  white-space: nowrap;

  &:hover {
    color: #111827;
    background-color: rgba(246, 188, 0, 0.1);
  }

  &.is-active {
    color: #111827;
    background-color: rgba(246, 188, 0, 0.18);
    font-weight: 600;
  }
}

:is(.dark) .nav-shortcut-link {
  color: #9ca3af;

  &:hover {
    color: #f9fafb;
    background-color: rgba(246, 188, 0, 0.12);
  }

  &.is-active {
    color: #facc15;
    background-color: rgba(246, 188, 0, 0.16);
    font-weight: 600;
  }
}
</style>
