/**
 * Placeholder playlists for Hoops FE redesign.
 * Real 20-level lists will replace these when the team delivers them.
 * Backend still receives real file ids (stems); UI may show 1..N.
 *
 * Casual 001…, level 14…, DK* advanced; tournament from source_group/-- (14–23).
 * Avoid Challenge* names in placeholder lists.
 */

/** Quick Play (1P) — casual 001–011 + level 14–22. */
export const QUICK_PLAY_LEVELS = [
  '001', '002', '003', '004', '005', '006', '007', '008', '009', '010', '011',
  '14', '15', '16', '17', '18', '19', '20', '21', '22',
]

/** Team Battle (2P) — DK advanced + level 14–23 to fill 20 placeholders. */
export const TEAM_BATTLE_LEVELS = [
  'DK01', 'DK02', 'DK03', 'DK04', 'DK05', 'DK06', 'DK07', 'DK08', 'DK09', 'DK10',
  '14', '15', '16', '17', '18', '19', '20', '21', '22', '23',
]

/**
 * Tournament playlist order (matches games/source_group/-- /
 * corporate Advance 14→23).
 */
export const TOURNAMENT_LEVEL_ORDER = [
  '14', '15', '16', '17', '18', '19', '20', '21', '22', '23',
]

export const HOW_TO = {
  single:
    'Hit the lit hoops before they expire. Clear each wave to advance.',
  multi:
    'Each player scores their own colour. Clear targets together to progress.',
  group:
    'A fixed set of levels runs in order. No level pick — just play through 1, 2, 3… as a group session.',
}

/** Bullet copy for Setup screen (mock-style how-to). */
export const HOW_TO_BULLETS = {
  single: [
    'Watch which hoops light up on the floor.',
    'Hit the lit hoops before they expire.',
    'Clear each wave to advance to the next level.',
  ],
  multi: [
    'Each player scores their own colour on the floor.',
    'Clear your targets together to progress.',
    'Stay sharp — missed hoops cost lives.',
  ],
  group: [
    'A fixed tournament set runs in order — no level pick.',
    'Play through levels 1, 2, 3… as a group session.',
    'Clear each stage to keep moving.',
  ],
}

export function playlistForMode(playMode) {
  if (playMode === 'multi') return TEAM_BATTLE_LEVELS
  if (playMode === 'group') return TOURNAMENT_LEVEL_ORDER
  return QUICK_PLAY_LEVELS
}

/** Map backend level stem → UI number (1-based) within the active playlist. */
export function displayLevelNumber(playMode, levelId) {
  const stem = String(levelId ?? '')
    .replace(/\.(led|ledb)$/i, '')
    .trim()
  if (!stem || stem === 'auto') return null
  const list = playlistForMode(playMode)
  const idx = list.findIndex(
    (id) => id === stem || stem.startsWith(id) || id.startsWith(stem)
  )
  if (idx >= 0) return idx + 1
  if (/^\d+$/.test(stem)) return Number(stem)
  return null
}

export function formatLevelLabel(playMode, levelId) {
  const n = displayLevelNumber(playMode, levelId)
  if (n != null) return String(n)
  return String(levelId ?? '—')
}
