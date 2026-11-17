import type { ReportContent, ReportSection } from '../api/reports'
import type { Registry } from '../api/types'
import { buildMermaid } from '../projects/map'
import { activity, componentMap, erDiagram, sequence, stateDiagram } from '../study/mermaid'

/**
 * The Mermaid source for one diagram section of a report (ADR 0025), generated from the same
 * study model the viewer draws, so a report and the viewer can't disagree. The compact component
 * map is the top level only; a sub-system is one component's children, one level, so a big
 * system comes out as a map plus one page per part. Null when the model no longer has what the
 * section points at (the study changed since the preset was saved).
 */
export function diagramCode(
  section: Extract<ReportSection, { type: 'diagram' }>,
  study: ReportContent['study'],
  registry: Registry | undefined,
): string | null {
  if (section.diagram === 'group') {
    if (!registry || !section.group) return null
    return buildMermaid(registry, { group: section.group })
  }
  const model = study?.model
  if (!model) return null
  switch (section.diagram) {
    case 'map':
      return componentMap(model, { focus: section.focus ?? null, depth: 0 }) || null
    case 'flow': {
      const flow = model.flows.find((f) => f.id === section.ref)
      return flow ? sequence(flow, model.components) : null
    }
    case 'activity': {
      const found = model.activities.find((a) => a.id === section.ref)
      return found ? activity(found) : null
    }
    case 'state': {
      const found = model.states.find((s) => s.id === section.ref)
      return found ? stateDiagram(found) : null
    }
    case 'schema':
      return model.entities.length ? erDiagram(model.entities) : null
  }
}

/** The section's heading, numbered in the order the reader chose. */
export const heading = (index: number, section: { title: string }) => `${index + 1}. ${section.title}`

/** `@page` rules for the report's page options. */
export function pageCss(options: { page_size: string; orientation: string }): string {
  const size = options.page_size === 'Letter' ? 'Letter' : 'A4'
  const orientation = options.orientation === 'landscape' ? 'landscape' : 'portrait'
  return `@page { size: ${size} ${orientation}; margin: 16mm 14mm 18mm; }`
}
