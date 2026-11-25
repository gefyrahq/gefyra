<script setup lang="ts">
interface UseCase {
  title: string
  subHeader: string
  text: string
  managerValue: string
  developerValue: string
  icon: string
  mermaid: string
}

const useCases: UseCase[] = [
  {
    title: 'Enterprise-Compliant Local Development (Podman Native)',
    subHeader: 'No Root. No Docker Desktop Fees. Zero Security Compromises.',
    text: 'Gefyra integrates seamlessly with native Podman and daemonless container environments. Developers bridge their local code directly into Kubernetes without requiring root privileges or violating strict corporate IT security policies.',
    managerValue: 'Full alignment with Zero-Trust and RBAC policies; eliminates third-party container licensing friction.',
    developerValue: 'Native Linux and Podman support without clunky VM workarounds or permission headaches.',
    icon: 'i-lucide-shield-check',
    mermaid: `flowchart TB
    subgraph Host
        direction TB
        HostTitle[["Local Workstation"]] ~~~ User["Non-Root Dev"]
        User --> Podman["Podman"]
        Podman --> Cargo["Gefyra Cargo"]
    end
    Cargo <==>|WireGuard| Stowaway
    subgraph Cluster
        direction TB
        ClusterTitle[["K8s Staging"]] ~~~ Stowaway["Stowaway"]
        Stowaway --> Operator["Operator"]
        Operator --> Pods["Pods"]
    end
    classDef groupTitle fill:transparent,stroke:none;
    classDef devBox stroke-width:2px;
    classDef k8sBox stroke-width:2px;
    class HostTitle,ClusterTitle groupTitle;
    class Host devBox;
    class Cluster k8sBox;`,
  },
  {
    title: 'Parallel Testing in Shared Enterprise Clusters',
    subHeader: 'Stop Burning Cloud Budget on Single-User Staging Environments.',
    text: 'Scale your engineering team on a single, powerful shared Kubernetes cluster. Powered by Gefyra’s rewritten operator architecture, User-Specific Bridges isolate traffic per namespace. No matter how large your team is or grows, every single developer can test simultaneously without traffic collisions.',
    managerValue: 'Cuts cloud staging infrastructure costs by up to 70% while supporting unlimited team scaling.',
    developerValue: 'Isolated sandbox testing inside real, high-performance shared clusters with zero risk of interfering with teammates.',
    icon: 'i-lucide-users',
    mermaid: `flowchart TB
    subgraph Developers
        direction TB
        TeamTitle[["Engineering Team"]] ~~~ DevA["Alice"]
        TeamTitle ~~~ DevB["Bob"]
    end

    DevA <==>|Bridge A| CarrierA
    DevB <==>|Bridge B| CarrierB

    subgraph Cluster
        direction TB
        ClusterTitle[["Shared Staging"]] ~~~ NSA
        ClusterTitle ~~~ NSB
        subgraph NSA
            direction TB
            BillingTitle[["billing ns"]] ~~~ CarrierA["Carrier A"]
            CarrierA --- BillingSvc["Billing"]
        end
        subgraph NSB
            direction TB
            AuthTitle[["auth ns"]] ~~~ CarrierB["Carrier B"]
            CarrierB --- AuthSvc["Auth"]
        end
    end

    classDef groupTitle fill:transparent,stroke:none;
    classDef teamAlice stroke-width:2px;
    classDef teamBob stroke-width:2px;
    class TeamTitle,ClusterTitle,BillingTitle,AuthTitle groupTitle;
    class NSA,DevA teamAlice;
    class NSB,DevB teamBob;`,
  },
  {
    title: 'Live Remote Debugging with Real Cluster Data',
    subHeader: 'Set Breakpoints in Local Code While Intercepting Live Cluster Traffic.',
    text: 'Stop wasting hours building brittle local mocks or docker-compose setups that inevitably drift from production. Gefyra routes live traffic from your target Kubernetes cluster straight into your familiar local IDE (VS Code, IntelliJ, PyCharm).',
    managerValue: 'Drastically reduces "works on my machine" bugs leaking into staging or production.',
    developerValue: 'Step-through debugging against real cloud databases, microservices, and live environment states.',
    icon: 'i-lucide-bug',
    mermaid: `sequenceDiagram
    participant Ingress as Ingress
    participant Carrier as Carrier2
    participant IDE as Local IDE
    participant DB as Staging DB

    Ingress->>Carrier: Incoming request
    Carrier->>IDE: Tunnel to local
    Note over IDE: Breakpoint
    IDE->>DB: Query Postgres
    DB-->>IDE: Live data
    IDE-->>Carrier: Response
    Carrier-->>Ingress: HTTP 200`,
  },
  {
    title: 'Instant Feedback Loops (Save & See)',
    subHeader: 'Eliminate the 15-Minute CI/CD Build-and-Push Penalty.',
    text: 'Gefyra overlays containers in Kubernetes with your local code in real time. Validate frontend updates, API payloads, or core business logic instantly inside the target cluster context—without building or pushing a single Docker image.',
    managerValue: 'Maximizes engineering velocity, developer throughput, and time-to-market.',
    developerValue: 'Immediate feedback on every code change; zero context switching while waiting for pipelines.',
    icon: 'i-lucide-zap',
    mermaid: `flowchart TB
    Dev["1. Developer"] -->|Hit Save| Local["2. Local Container"]
    Local <==>|Live Overlay| K8sPod["3. Staging Pod"]
    K8sPod -->|Verified| Client["4. Browser / API"]
    classDef gefyra stroke-width:2px;
    class Dev,Local,K8sPod,Client gefyra;`,
  },
  {
    title: 'Autonomous AI Agents in Native Kubernetes',
    subHeader: 'Eliminate the CI/CD Penalty for AI-Generated Code and Agent Workflows.',
    text: 'Gefyra bridges your AI agent’s local execution environment directly with your Kubernetes staging cluster using real-time container overlaying. Your AI agent accesses real K8s services, internal databases, and cluster-internal DNS names locally. Inbound cluster traffic routes seamlessly to the agent\'s local code, allowing autonomous code generation, feature updates, and bug fixes to be validated instantly under real cluster conditions—without building or pushing a single Docker image.',
    managerValue: 'Drastically reduces LLM execution costs and token usage by shrinking the AI feedback loop from 15-minute CI/CD pipelines to milliseconds. Accelerates time-to-market for AI features with guaranteed production compatibility.',
    developerValue: 'Instant validation of AI-generated code against real cluster dependencies; zero context switching while waiting for builds, with full IDE debugging capabilities for local agent pipelines.',
    icon: 'i-lucide-brain',
    mermaid: `flowchart TB
    subgraph LocalMachine
        direction TB
        LocalTitle[["AI Workspace"]] ~~~ AIAgent["AI Agent"]
        AIAgent --> Container["Container"]
    end

    Container <==>|WireGuard| Staging

    subgraph RemoteK8s
        direction TB
        RemoteTitle[["Cluster Ground Truth"]] ~~~ Staging["Staging Pod"]
        Staging --> LiveDB[("Live DB")]
    end

    LiveDB -.->|Feedback| AIAgent
    classDef groupTitle fill:transparent,stroke:none;
    classDef agentBox stroke-width:2px;
    classDef clusterBox stroke-width:2px;
    class LocalTitle,RemoteTitle groupTitle;
    class LocalMachine agentBox;
    class RemoteK8s clusterBox;`,
  },
]
</script>

<template>
  <UPageSection class="border-t">
    <template #title>
      Gefyra Use Cases
    </template>

    <template #description>
      From enterprise compliance to instant feedback — five ways Gefyra accelerates Kubernetes development.
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
              class="use-case-accent use-case-index inline-flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
            >
              {{ index + 1 }}
            </span>
            <UIcon
              :name="useCase.icon"
              class="use-case-accent size-5 shrink-0"
            />
          </div>

          <ProseH2 class="!mt-0">
            {{ useCase.title }}
          </ProseH2>

          <p class="use-case-accent text-base font-semibold text-pretty sm:text-lg">
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

        <div class="use-case-mermaid w-full flex-1 rounded-xl border border-default/20 bg-muted/10 p-4 sm:p-6 lg:max-w-1/2">
          <DeferredMermaid :code="useCase.mermaid" />
        </div>
      </article>
    </div>
  </UPageSection>
</template>
