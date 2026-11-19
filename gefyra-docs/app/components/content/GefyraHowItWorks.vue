<script setup lang="ts">
const steps = [
  {
    title: 'gefyra up',
    description: 'Prepares your local engine environment and establishes an encrypted WireGuard tunnel directly to your target cluster.',
  },
  {
    title: 'gefyra run',
    description: 'Starts your local Docker/Podman container directly inside the cluster network with internal DNS and database access.',
  },
  {
    title: 'gefyra mount & bridge create',
    description: 'Mounts the cluster workload and routes live ingress/HTTP traffic into your local container based on path or header rules.',
  },
  {
    title: 'gefyra down',
    description: 'Clean exit. Removes active bridges, unmounts workloads, and restores original cluster state with zero leftover footprints.',
  },
] as const
</script>

<template>
  <ol class="how-it-works">
    <li
      v-for="(step, index) in steps"
      :key="step.title"
      class="how-it-works-step"
      :class="{ 'is-active': index === 2 }"
    >
      <span
        class="how-it-works-index"
        aria-hidden="true"
      >{{ index + 1 }}</span>
      <div class="how-it-works-copy">
        <h3 class="how-it-works-title">
          {{ step.title }}
        </h3>
        <p class="how-it-works-description">
          {{ step.description }}
        </p>
      </div>
    </li>
  </ol>
</template>
