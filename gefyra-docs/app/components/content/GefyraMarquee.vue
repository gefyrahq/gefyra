<template>
  <UContainer>
    <ProseH3 class="text-center">
      All Programming Languages and Frameworks.
    </ProseH3>

    <ProseP class="text-base sm:text-lg text-muted text-center text-balance mt-6 mb-12">
      If it can run in a container, you can develop it with Gefyra. It seamlessly supports all platforms that support Docker or Podman, and <b>all programming languages and frameworks</b> that can be run in a container. No limitations, no custom plugins required.
    </ProseP>

    <ClientOnly>
      <UMarquee>
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
      </UMarquee>
      <template #fallback>
        <div
          class="flex flex-wrap items-center justify-center gap-6 py-4 opacity-80"
          aria-hidden="true"
        >
          <UIcon
            name="i-mdi-apple"
            class="size-10 shrink-0"
          />
          <UIcon
            name="i-simple-icons-linux"
            class="size-10 shrink-0"
          />
          <UIcon
            name="i-mdi-language-python"
            class="size-10 shrink-0"
          />
          <UIcon
            name="i-mdi-language-typescript"
            class="size-10 shrink-0"
          />
          <UIcon
            name="i-mdi-vuejs"
            class="size-10 shrink-0"
          />
        </div>
      </template>
    </ClientOnly>
  </UContainer>
</template>
