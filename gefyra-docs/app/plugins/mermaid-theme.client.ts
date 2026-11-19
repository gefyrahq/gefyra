/**
 * Mermaid bakes themeVariables into SVG <style> blocks with #svgId selectors
 * and !important. Page CSS cannot override those. Inject matching #svgId rules
 * that resolve --mm-* tokens, appended AFTER Mermaid's own <style> so we win.
 */
function THEME_STYLE(id: string) {
  return `
#${id} .node rect,
#${id} .node polygon,
#${id} .node circle,
#${id} .node path {
  fill: var(--mm-node-bg) !important;
  stroke: var(--mm-node-border) !important;
}
#${id} .label text,
#${id} .node text,
#${id} .nodeLabel,
#${id} .label,
#${id} span.nodeLabel,
#${id} div.nodeLabel,
#${id} .node foreignObject div,
#${id} .node foreignObject span,
#${id} .messageText {
  fill: var(--mm-text) !important;
  color: var(--mm-text) !important;
}
#${id} .edgePath .path,
#${id} .flowchart-link,
#${id} .messageLine0,
#${id} .messageLine1 {
  stroke: var(--mm-line) !important;
}
#${id} .marker {
  fill: var(--mm-line) !important;
  stroke: var(--mm-line) !important;
}
#${id} .cluster rect {
  fill: var(--mm-cluster-bg) !important;
  stroke: var(--mm-cluster-border) !important;
}
#${id} .node.groupTitle rect,
#${id} .node.groupTitle polygon {
  fill: transparent !important;
  stroke: transparent !important;
}
#${id} .node.groupTitle .nodeLabel,
#${id} .node.groupTitle span,
#${id} .node.groupTitle text {
  fill: var(--mm-title) !important;
  color: var(--mm-title) !important;
}
#${id} .actor {
  fill: var(--mm-actor-bg) !important;
  stroke: var(--mm-actor-border) !important;
}
#${id} text.actor,
#${id} .actor text,
#${id} text.actor tspan {
  fill: var(--mm-actor-text) !important;
  color: var(--mm-actor-text) !important;
}
#${id} .actor-line {
  stroke: var(--mm-actor-line) !important;
}
#${id} .note {
  fill: var(--mm-note-bg) !important;
  stroke: var(--mm-note-border) !important;
}
#${id} .noteText {
  fill: var(--mm-note-text) !important;
}
/* Edge / arrow labels — Mermaid bakes light edgeLabelBackground onto .labelBkg / .edgeLabel p */
#${id} .edgeLabel rect,
#${id} .edgeLabel > g > rect,
#${id} .edgeLabels .edgeLabel rect {
  fill: var(--mm-edge-label-bg) !important;
  stroke: var(--mm-cluster-border) !important;
  opacity: 1 !important;
}
#${id} .labelBkg,
#${id} span.edgeLabel,
#${id} .edgeLabel p {
  background-color: var(--mm-edge-label-bg) !important;
  background: var(--mm-edge-label-bg) !important;
}
#${id} .edgeLabel,
#${id} .edgeLabel text,
#${id} .edgeLabel span,
#${id} .edgeLabel p,
#${id} .edgeLabel div,
#${id} .edgeLabel foreignObject div,
#${id} .edgeLabel foreignObject span,
#${id} .edgeLabel foreignObject p,
#${id} .labelBkg,
#${id} .labelBkg span,
#${id} .labelBkg p {
  fill: var(--mm-text) !important;
  color: var(--mm-text) !important;
}
/* Node HTML labels also need explicit p/color (Mermaid sets color:#78350f on span) */
#${id} .node .label p,
#${id} .node .nodeLabel p,
#${id} .node foreignObject p,
#${id} .node foreignObject div {
  color: inherit !important;
}
#${id} .node.trad rect,
#${id} .node.blind rect,
#${id} .node.danger rect,
#${id} .cluster.trad > rect,
#${id} .cluster.blind > rect,
#${id} .cluster.danger > rect {
  fill: var(--mm-danger-bg) !important;
  stroke: var(--mm-danger-border) !important;
}
#${id} .node.trad .nodeLabel, #${id} .node.blind .nodeLabel, #${id} .node.danger .nodeLabel,
#${id} .node.trad text, #${id} .node.blind text, #${id} .node.danger text,
#${id} .node.trad span, #${id} .node.blind span, #${id} .node.danger span {
  fill: var(--mm-danger-text) !important;
  color: var(--mm-danger-text) !important;
}
#${id} .node.k8sBox rect, #${id} .node.remote rect, #${id} .node.clusterBox rect, #${id} .node.runBox rect,
#${id} .cluster.k8sBox > rect, #${id} .cluster.remote > rect, #${id} .cluster.clusterBox > rect, #${id} .cluster.runBox > rect {
  fill: var(--mm-remote-bg) !important;
  stroke: var(--mm-remote-border) !important;
}
#${id} .node.k8sBox .nodeLabel, #${id} .node.remote .nodeLabel, #${id} .node.clusterBox .nodeLabel, #${id} .node.runBox .nodeLabel,
#${id} .node.k8sBox text, #${id} .node.remote text, #${id} .node.clusterBox text, #${id} .node.runBox text,
#${id} .node.k8sBox span, #${id} .node.remote span, #${id} .node.clusterBox span, #${id} .node.runBox span {
  fill: var(--mm-remote-text) !important;
  color: var(--mm-remote-text) !important;
}
#${id} .node.teamAlice rect, #${id} .node.devBox rect, #${id} .node.gefyra rect, #${id} .node.safe rect,
#${id} .node.grounded rect, #${id} .node.overlay rect, #${id} .node.bridgeBox rect, #${id} .node.agentBox rect, #${id} .node.tunnelBox rect,
#${id} .cluster.teamAlice > rect, #${id} .cluster.devBox > rect, #${id} .cluster.gefyra > rect, #${id} .cluster.safe > rect,
#${id} .cluster.grounded > rect, #${id} .cluster.overlay > rect, #${id} .cluster.bridgeBox > rect, #${id} .cluster.agentBox > rect, #${id} .cluster.tunnelBox > rect {
  fill: var(--mm-brand-bg) !important;
  stroke: var(--mm-brand-border) !important;
}
#${id} .node.teamAlice .nodeLabel, #${id} .node.devBox .nodeLabel, #${id} .node.gefyra .nodeLabel, #${id} .node.safe .nodeLabel,
#${id} .node.grounded .nodeLabel, #${id} .node.overlay .nodeLabel, #${id} .node.bridgeBox .nodeLabel, #${id} .node.agentBox .nodeLabel, #${id} .node.tunnelBox .nodeLabel,
#${id} .node.teamAlice text, #${id} .node.devBox text, #${id} .node.gefyra text, #${id} .node.safe text,
#${id} .node.grounded text, #${id} .node.overlay text, #${id} .node.bridgeBox text, #${id} .node.agentBox text, #${id} .node.tunnelBox text,
#${id} .node.teamAlice span, #${id} .node.devBox span, #${id} .node.gefyra span, #${id} .node.safe span,
#${id} .node.grounded span, #${id} .node.overlay span, #${id} .node.bridgeBox span, #${id} .node.agentBox span, #${id} .node.tunnelBox span {
  fill: var(--mm-brand-text) !important;
  color: var(--mm-brand-text) !important;
}
#${id} .node.teamBob rect, #${id} .node.hook rect,
#${id} .cluster.teamBob > rect, #${id} .cluster.hook > rect {
  fill: var(--mm-alt-bg) !important;
  stroke: var(--mm-alt-border) !important;
}
#${id} .node.teamBob .nodeLabel, #${id} .node.hook .nodeLabel,
#${id} .node.teamBob text, #${id} .node.hook text,
#${id} .node.teamBob span, #${id} .node.hook span {
  fill: var(--mm-alt-text) !important;
  color: var(--mm-alt-text) !important;
}
`
}

function applyMermaidThemeOverrides(root: ParentNode = document) {
  root.querySelectorAll<SVGElement>('.mermaid svg[id]').forEach((svg) => {
    const rawId = svg.id
    if (!rawId) {
      return
    }
    const id = CSS.escape(rawId)
    const next = THEME_STYLE(id)
    let style = svg.querySelector<HTMLStyleElement>('style[data-gefyra-theme]')
    if (!style) {
      style = document.createElement('style')
      style.setAttribute('data-gefyra-theme', '')
    }
    // Always last so we beat Mermaid's baked #id … !important themeVariables
    if (style.parentNode !== svg || svg.lastChild !== style) {
      svg.appendChild(style)
    }
    if (style.textContent !== next) {
      style.textContent = next
    }
  })
}

export default defineNuxtPlugin(() => {
  const run = () => applyMermaidThemeOverrides()

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true })
  }
  else {
    run()
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        run()
        return
      }
    }
  })
  observer.observe(document.documentElement, { childList: true, subtree: true })
})
