<script setup lang="ts">
interface UseCase {
  title: string
  subHeader: string
  text: string
  managerValue: string
  developerValue: string
  icon: string
  image?: string
}

const useCases: UseCase[] = [
  {
    title: 'Enterprise-Compliant Local Development (Podman Native)',
    subHeader: 'No Root. No Docker Desktop Fees. Zero Security Compromises.',
    text: 'Gefyra integrates seamlessly with native Podman and daemonless container environments. Developers bridge their local code directly into Kubernetes without requiring root privileges or violating strict corporate IT security policies.',
    managerValue: 'Full alignment with Zero-Trust and RBAC policies; eliminates third-party container licensing friction.',
    developerValue: 'Native Linux and Podman support without clunky VM workarounds or permission headaches.',
    icon: 'i-lucide-shield-check',
  },
  {
    title: 'Parallel Testing in Shared Enterprise Clusters',
    subHeader: 'Stop Burning Cloud Budget on Single-User Staging Environments.',
    text: 'Scale your engineering team on a single, powerful shared Kubernetes cluster. Powered by Gefyra’s rewritten operator architecture, User-Specific Bridges isolate traffic per namespace. No matter how large your team is or grows, every single developer can test simultaneously without traffic collisions.',
    managerValue: 'Cuts cloud staging infrastructure costs by up to 70% while supporting unlimited team scaling.',
    developerValue: 'Isolated sandbox testing inside real, high-performance shared clusters with zero risk of interfering with teammates.',
    icon: 'i-lucide-users',
  },
  {
    title: 'Live Remote Debugging with Real Cluster Data',
    subHeader: 'Set Breakpoints in Local Code While Intercepting Live Cluster Traffic.',
    text: 'Stop wasting hours building brittle local mocks or docker-compose setups that inevitably drift from production. Gefyra routes live traffic from your target Kubernetes cluster straight into your familiar local IDE (VS Code, IntelliJ, PyCharm).',
    managerValue: 'Drastically reduces "works on my machine" bugs leaking into staging or production.',
    developerValue: 'Step-through debugging against real cloud databases, microservices, and live environment states.',
    icon: 'i-lucide-bug',
  },
  {
    title: 'Instant Feedback Loops (Save & See)',
    subHeader: 'Eliminate the 15-Minute CI/CD Build-and-Push Penalty.',
    text: 'Gefyra overlays containers in Kubernetes with your local code in real time. Validate frontend updates, API payloads, or core business logic instantly inside the target cluster context—without building or pushing a single Docker image.',
    managerValue: 'Maximizes engineering velocity, developer throughput, and time-to-market.',
    developerValue: 'Immediate feedback on every code change; zero context switching while waiting for pipelines.',
    icon: 'i-lucide-zap',
  },
  {
    title: 'Autonomous AI Agents in Native Kubernetes',
    subHeader: 'Eliminate the CI/CD Penalty for AI-Generated Code and Agent Workflows.',
    text: 'Gefyra bridges your AI agent’s local execution environment directly with your Kubernetes staging cluster using real-time container overlaying. Your AI agent accesses real K8s services, internal databases, and cluster-internal DNS names locally. Inbound cluster traffic routes seamlessly to the agent\'s local code, allowing autonomous code generation, feature updates, and bug fixes to be validated instantly under real cluster conditions—without building or pushing a single Docker image.',
    managerValue: 'Drastically reduces LLM execution costs and token usage by shrinking the AI feedback loop from 15-minute CI/CD pipelines to milliseconds. Accelerates time-to-market for AI features with guaranteed production compatibility.',
    developerValue: 'Instant validation of AI-generated code against real cluster dependencies; zero context switching while waiting for builds, with full IDE debugging capabilities for local agent pipelines.',
    icon: 'i-lucide-brain',
  },
]
</script>

<template>
  <UPageSection class="border-t">
    <template #title>
      Gefyra Use Cases
    </template>

    <template #description>
      From enterprise compliance to instant feedback — four ways Gefyra accelerates Kubernetes development.
    </template>

    <div class="flex flex-col gap-16 sm:gap-24">
      <article
        v-for="(useCase, index) in useCases"
        :key="useCase.title"
        class="flex flex-col items-center justify-between gap-8 lg:flex-row lg:gap-12"
        :class="{ 'lg:flex-row-reverse': index % 2 === 1 }"
      >
        <div class="flex flex-1 flex-col gap-4 lg:max-w-1/2">
          <div class="flex items-center gap-3">
            <span
              class="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary"
            >
              {{ index + 1 }}
            </span>
            <UIcon
              :name="useCase.icon"
              class="size-5 shrink-0 text-primary"
            />
          </div>

          <ProseH2 class="!mt-0">
            {{ useCase.title }}
          </ProseH2>

          <p class="text-base font-semibold text-primary text-pretty sm:text-lg">
            {{ useCase.subHeader }}
          </p>

          <ProseP class="!mt-0">
            {{ useCase.text }}
          </ProseP>

          <div class="mt-2 grid gap-4 sm:grid-cols-2">
            <UPageFeature
              icon="i-lucide-briefcase-business"
              title="Manager Value"
              :description="useCase.managerValue"
              orientation="vertical"
            />
            <UPageFeature
              icon="i-lucide-code-xml"
              title="Developer Value"
              :description="useCase.developerValue"
              orientation="vertical"
            />
          </div>
        </div>

        <div class="w-full flex-1 overflow-hidden lg:max-w-1/2">
          <NuxtImg
            v-if="useCase.image"
            :src="useCase.image"
            :alt="useCase.title"
            class="w-full rounded-xl"
            loading="lazy"
            format="webp"
          />
          <div
            v-else
            class="flex aspect-[4/3] w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-default bg-elevated/50 text-muted"
            role="img"
            :aria-label="`Placeholder image for ${useCase.title}`"
          >
            <UIcon
              :name="useCase.icon"
              class="size-12 opacity-40"
            />
            <span class="text-sm font-medium tracking-wide uppercase">
              Image placeholder
            </span>
            <span class="max-w-56 text-center text-xs opacity-70">
              {{ useCase.title }}
            </span>
          </div>
        </div>
      </article>
    </div>
  </UPageSection>
</template>
