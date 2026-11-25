<script setup lang="ts">
const traditional = `flowchart TB
    T1["1. Code Change"] --> T2["2. Docker Build (3 min)"]
    T2 --> T3["3. Registry Push (2 min)"]
    T3 --> T4["4. Deploy K8s (1 min)"]
    T4 --> T5["5. Pull & Schedule (2 min)"]
    T5 --> T6["6. Verification (10 min)"]
    classDef trad stroke-width:2px;
    class T1,T2,T3,T4,T5,T6 trad;`

const gefyra = `flowchart TB
    G1["1. Code Change"] -->|Hit Save| G2["2. Instant Hot-Reload (1s)"]
    G2 -->|WireGuard| G3["3. Live Verification (3s)"]
    classDef gefyra stroke-width:2px;
    class G1,G2,G3 gefyra;`
</script>

<template>
  <div>
    <div class="inner-loop-card inner-loop-trad">
      <p>
        <strong>Traditional Kubernetes Loop — 15 to 25 minutes per change</strong>
      </p>
      <DeferredMermaid :code="traditional" />
    </div>

    <div class="inner-loop-card inner-loop-gefyra">
      <p>
        <strong>Gefyra Loop — 3 seconds per change</strong>
      </p>
      <DeferredMermaid :code="gefyra" />
    </div>
  </div>
</template>
