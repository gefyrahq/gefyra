<script setup lang="ts">
const traditional = `%%{init: {'flowchart': {'padding': 28, 'nodeSpacing': 36, 'rankSpacing': 48, 'diagramPadding': 20}, 'themeVariables': { 'fontSize': '14px' }}}%%
flowchart LR
    T1["1. Code<br/>Change"] --> T2["2. Docker Build<br/>(3 mins)"] --> T3["3. Registry Push<br/>(2 mins)"] --> T4["4. Deploy K8s<br/>(1 min)"] --> T5["5. Pull & Schedule<br/>(2 mins)"] --> T6["6. Verification<br/>(10 mins)"]
    classDef trad stroke-width:2px;
    class T1,T2,T3,T4,T5,T6 trad;`

const gefyra = `%%{init: {'flowchart': {'padding': 28, 'nodeSpacing': 52, 'rankSpacing': 56, 'diagramPadding': 20}, 'themeVariables': { 'fontSize': '14px' }}}%%
flowchart LR
    G1["1. Code<br/>Change"] -->|Hit Save| G2["2. Instant Hot-Reload<br/>(1 second)"] -->|WireGuard Link| G3["3. Live Verification<br/>(3 seconds)"]
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
