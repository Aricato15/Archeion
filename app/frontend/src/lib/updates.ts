/** The update notes in docs/updates/, named update-vX.Y.Z.md: the version in the name is the one they update to. */
export type UpdateNote = { version: string; path: string }

const NOTE = /(?:^|\/)updates\/update-v(\d+\.\d+\.\d+)\.md$/

/** Compare two MAJOR.MINOR.PATCH versions: negative when a is older. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0)
    if (d !== 0) return d
  }
  return 0
}

/** The notes among a list of doc paths, newest target version first. */
export function updateNotes(paths: string[]): UpdateNote[] {
  return paths
    .flatMap((path) => {
      const m = NOTE.exec(path)
      return m ? [{ version: m[1], path }] : []
    })
    .sort((a, b) => compareVersions(b.version, a.version))
}
