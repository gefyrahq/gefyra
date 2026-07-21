<script setup lang="ts">

</script>

<template>
  <UPageSection class="border-t">
    <template #title>
      Gefyra Usecases
    </template>

    <div class="flex flex-col items-center justify-between gap-4 md:flex-row">
      <div class="md:max-w-1/2">
        <ProseH2>
          Kubernetes as Development Platform
        </ProseH2>

        <ProseP>
          Local containers on board! If you want to use Kubernetes as your development platform, Gefyra is the right tool for you. It <strong>enables you to run your code in Kubernetes</strong> without the need to build and push containers. Gefyra overlays the container in Kubernetes with <strong> your local container</strong>. Instantly see the <strong>effects of your code changes</strong> in Kubernetes.
        </ProseP>

        <ProseP>
          The highest possible development velocity is achieved by using Gefyra in combination with a <strong>local or remote Kubernetes cluster</strong>.
        </ProseP>

        <UButton
          to="https://www.blueshoe.io/blog/alternative-to-telepresence-2-gefyra/"
          target="_blank"
          size="xl"
          trailing-icon="i-lucide-arrow-right"
        >
          See Gefrya in Action
        </UButton>
      </div>

      <div class="md:max-w-1/2 overflow-hidden">
        <img
          src="/img/run.svg"
          class="run-icon"
          mode="svg"
        >
      </div>
    </div>

    <div class="flex flex-col items-center justify-between gap-4 md:flex-row">
      <div class="md:max-w-1/2 md:order-2">
        <ProseH2>
          Shared Kubernetes-based Resources
        </ProseH2>

        <ProseP>
          Suppose you are working on a feature that requires collaboration with other team members, such as frontend developers, backend engineers, and database administrators. With Gefyra, you can <strong>create a shared environment accessible to the entire team</strong>.
        </ProseP>

        <ProseP>
          Each team member can work on their respective components while having shared resources available (for example a large database). Gefyra <strong>enables you to share your local code with your team</strong> and <strong>collaborate on a shared environment</strong>.
        </ProseP>
      </div>

      <div class="md:max-w-1/2 overflow-hidden md:order-1">
        <img
          src="/img/bridge.svg"
          class="run-icon"
          mode="svg"
        >
      </div>
    </div>
  </UPageSection>
</template>
