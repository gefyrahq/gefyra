<script setup lang="ts">
const features = [
  {
    icon: 'i-lucide-zap',
    title: 'Supercharge Development Speed',
    description: 'Zero-Build Live Development. Gefyra temporarily intercepts cluster pods and transparently routes the traffic to your local container runtime. This cuts down feedback loops by 90% and allows engineers to spot and fix environment bugs in seconds.',
  },
  {
    icon: 'i-lucide-container',
    title: 'Native Podman & Docker Support',
    description: 'Daemonless Container Engine Compatibility. Gefyra runs flawlessly on Docker Desktop, Rancher Desktop, and native Podman environments. It seamlessly aligns with strict corporate security policies by allowing developers to work rootless under Linux.',
  },
  {
    icon: 'i-lucide-users',
    title: 'Shared Staging Clusters at Enterprise Scale',
    description: 'User Specific Bridges. Gefyra’s operator architecture isolates network bridges per individual developer. No matter how large your engineering team is or grows, every single developer can safely test and debug inside the exact same shared staging cluster simultaneously — each working securely within their own assigned namespace, with zero traffic collisions.',
  },
  {
    icon: 'i-lucide-shield-check',
    title: 'Secure Namespace & RBAC Isolation',
    description: 'Granular Kubernetes Enclosure. Gefyra restricts all local connections tightly within the developer\'s pre-assigned Kubernetes namespaces. Platform teams can confidently greenlight the tool because it fully respects existing RBAC policies without requiring global cluster-admin rights.',
  },
  {
    icon: 'i-lucide-bug',
    title: 'Fight Environment Bugs',
    description: 'Shared Kubernetes-based Resources. Your local code execution interacts natively with internal cluster databases, private APIs, and cloud microservices. This eliminates the need for fragile local mocks and guarantees testing under real production-like dependencies from day one.',
  },
  {
    icon: 'i-lucide-laptop',
    title: 'Flexible Workflows',
    description: 'Direct IDE & Debugger Integration. Connect live remote cluster traffic seamlessly to local breakpoints in VS Code, IntelliJ, or PyCharm. Developers can diagnose heavy cloud bugs using the powerful, familiar desktop tools they love instead of digging through chaotic log files.',
  },
] as const
</script>

<template>
  <ul class="gefyra-features">
    <li
      v-for="feature in features"
      :key="feature.title"
      class="gefyra-feature"
    >
      <UIcon
        :name="feature.icon"
        class="gefyra-feature-icon"
      />
      <h3 class="gefyra-feature-title">
        {{ feature.title }}
      </h3>
      <p class="gefyra-feature-description">
        {{ feature.description }}
      </p>
    </li>
  </ul>
</template>
