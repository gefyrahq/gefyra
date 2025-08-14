<script setup lang="ts">
import { UIcon, UPageMarquee, UPageSection } from '#components'
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
        <UIcon
          name="i-gefyra-run"
          class="run-icon"
          mode="svg"
        />
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
        <UIcon
          name="i-gefyra-run"
          class="run-icon"
          mode="svg"
        />
      </div>
    </div>

    <div>
      <ProseH2>
        All Programming Languages and Frameworks
      </ProseH2>

      <ProseP>
        If it can run in a container, you can develop it in a container. Gefyra <strong>supports all platforms</strong> that support Docker, and <strong>all programming languages and frameworks</strong> that can be run in a container.
      </ProseP>

      <ProseP>
        Find one of our <strong>example projects</strong> for container-based development with Gefyra and get started in no time. Be a Dev/Prod-parity hero!
      </ProseP>
    </div>

    <UPageMarquee>
      <UIcon
        name="i-mdi-apple"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-microsoft-windows"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-linux"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-go"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-django"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-hugo"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-language-rust"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-language-python"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-language-java"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-language-typescript"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-express"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-angular"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-vuejs"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-simple-icons-fastapi"
        class="size-10 shrink-0"
      />
      <UIcon
        name="i-mdi-language-php"
        class="size-10 shrink-0"
      />
    </UPageMarquee>
  </UPageSection>
</template>
