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
    mermaid: `%%{init: {'themeVariables': { 'fontSize': '16px' }}}%%
flowchart TD
    subgraph Host["Developer Workstation (Linux / macOS)"]
        direction LR
        User["Non-Root Developer"] -->|Runs without sudo| Podman["Podman / Docker Engine"]
        Podman --> Cargo["Gefyra Cargo Sidecar"]
    end
    Cargo <==>|"Encrypted WireGuard Link (UDP 31820)"| Stowaway
    subgraph Cluster["Enterprise Kubernetes Staging Cluster"]
        direction LR
        Stowaway["Gefyra Stowaway"] --> Operator["Gefyra Operator"]
        Operator --> Pods["Staging Pods & Services"]
    end
    classDef devBox fill:#1d2a2f,stroke:#f6bc00,stroke-width:2px,color:#f8fafc;
    classDef k8sBox fill:#1d2a2f,stroke:#6b9ba5,stroke-width:2px,color:#f8fafc;
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
    mermaid: `flowchart LR
    subgraph Developers["Engineering Team"]
        DevA["Developer Alice"]
        DevB["Developer Bob"]
    end

    subgraph Cluster["Shared Staging Cluster (Zero Collisions)"]
        subgraph NSA["Namespace: team-billing"]
            CarrierA["Carrier2 (Alice's Bridge)"]
            BillingSvc["Billing Service"]
        end
        subgraph NSB["Namespace: team-auth"]
            CarrierB["Carrier2 (Bob's Bridge)"]
            AuthSvc["Auth Service"]
        end
    end

    DevA <==>|Isolated Bridge A| CarrierA
    DevB <==>|Isolated Bridge B| CarrierB
    classDef teamAlice fill:#1d2a2f,stroke:#f6bc00,stroke-width:2px,color:#facc15;
    classDef teamBob fill:#2d3b41,stroke:#6b9ba5,stroke-width:2px,color:#e0eced;
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
    mermaid: `%%{init: {'themeVariables': { 'fontSize': '18px', 'actorFontSize': '18px', 'messageFontSize': '17px', 'noteFontSize': '16px' }}}%%
sequenceDiagram
    participant Ingress as K8s Ingress
    participant Carrier as Carrier2 Proxy
    participant IDE as Local IDE
    participant DB as Remote Cluster DB

    Ingress->>Carrier: Incoming User Request
    Carrier->>IDE: Intercept & tunnel to local container
    Note over IDE: Breakpoint triggers in local editor
    IDE->>DB: Query remote Postgres / Redis
    DB-->>IDE: Live cluster dataset returned
    IDE-->>Carrier: Return response from local code
    Carrier-->>Ingress: Forward HTTP 200 to client`,
  },
  {
    title: 'Instant Feedback Loops (Save & See)',
    subHeader: 'Eliminate the 15-Minute CI/CD Build-and-Push Penalty.',
    text: 'Gefyra overlays containers in Kubernetes with your local code in real time. Validate frontend updates, API payloads, or core business logic instantly inside the target cluster context—without building or pushing a single Docker image.',
    managerValue: 'Maximizes engineering velocity, developer throughput, and time-to-market.',
    developerValue: 'Immediate feedback on every code change; zero context switching while waiting for pipelines.',
    icon: 'i-lucide-zap',
    mermaid: `%%{init: {'themeVariables': { 'fontSize': '18px' }}}%%
flowchart TD
    Dev["1. Developer (Editor)"] -->|"Hit Save (0.1s)"| Local["2. Local Container (Hot-Reload)"]
    Local <==>|"Live Container Overlay"| K8sPod["3. Staging K8s Pod"]
    K8sPod -->|"Instant Verified Response"| Client["4. Browser / Client API"]
    classDef gefyra fill:#1d2a2f,stroke:#f6bc00,stroke-width:2px,color:#facc15;
    class Dev,Local,K8sPod,Client gefyra;`,
  },
  {
    title: 'Autonomous AI Agents in Native Kubernetes',
    subHeader: 'Eliminate the CI/CD Penalty for AI-Generated Code and Agent Workflows.',
    text: 'Gefyra bridges your AI agent’s local execution environment directly with your Kubernetes staging cluster using real-time container overlaying. Your AI agent accesses real K8s services, internal databases, and cluster-internal DNS names locally. Inbound cluster traffic routes seamlessly to the agent\'s local code, allowing autonomous code generation, feature updates, and bug fixes to be validated instantly under real cluster conditions—without building or pushing a single Docker image.',
    managerValue: 'Drastically reduces LLM execution costs and token usage by shrinking the AI feedback loop from 15-minute CI/CD pipelines to milliseconds. Accelerates time-to-market for AI features with guaranteed production compatibility.',
    developerValue: 'Instant validation of AI-generated code against real cluster dependencies; zero context switching while waiting for builds, with full IDE debugging capabilities for local agent pipelines.',
    icon: 'i-lucide-brain',
    mermaid: `%%{init: {'themeVariables': { 'fontSize': '18px' }}}%%
flowchart TD
    subgraph LocalMachine["Local Workspace (AI Agent)"]
        direction LR
        AIAgent["AI Agent<br/>(Cursor / Claude)"] -->|"Writes code & runs tests"| Container["Local Container<br/>(IDE / Dev)"]
    end

    Container <==>|"Gefyra WireGuard Tunnel"| Staging

    subgraph RemoteK8s["Remote Cluster Ground Truth"]
        direction LR
        Staging["Staging Pod"] --> LiveDB[("Live Staging DB / APIs")]
    end

    LiveDB -.->|"Live feedback & real runtime errors"| AIAgent
    classDef agentBox fill:#1d2a2f,stroke:#f6bc00,stroke-width:2px,color:#facc15;
    classDef clusterBox fill:#1d2a2f,stroke:#6b9ba5,stroke-width:2px,color:#f8fafc;
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

        <div class="w-full flex-1 overflow-hidden rounded-xl border border-default/20 bg-muted/10 p-2 sm:p-4 lg:max-w-1/2">
          <Mermaid :code="encodeURIComponent(useCase.mermaid)" />
        </div>
      </article>
    </div>
  </UPageSection>
</template>
