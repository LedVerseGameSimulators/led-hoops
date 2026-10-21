/** Client-side play/RFID context for reload resume (keyed by backend game_id). */
const PREFIX = 'hoops_game_resume:'

export function saveGameResumeContext(gameId, config) {
  if (!gameId || !config) return
  const payload = {
    game_id: gameId,
    playMode: config.playMode,
    playerCount: config.playerCount,
    cardId: config.cardId,
    cardId2: config.cardId2,
    playerName: config.playerName,
    playerName2: config.playerName2,
    minutesRemaining: config.minutesRemaining,
    minutesRemaining2: config.minutesRemaining2,
    sessionId: config.sessionId,
    groupId: config.groupId,
    rosterSize: config.rosterSize,
    rosterPlayerIds: config.rosterPlayerIds,
    sessionId2: config.sessionId2,
    groupId2: config.groupId2,
    rosterSize2: config.rosterSize2,
    rosterPlayerIds2: config.rosterPlayerIds2,
  }
  try {
    sessionStorage.setItem(`${PREFIX}${gameId}`, JSON.stringify(payload))
  } catch {
    /* quota / private mode */
  }
}

export function loadGameResumeContext(gameId) {
  if (!gameId) return null
  try {
    const raw = sessionStorage.getItem(`${PREFIX}${gameId}`)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (data?.game_id !== gameId) return null
    return data
  } catch {
    return null
  }
}

export function clearGameResumeContext(gameId) {
  if (!gameId) return
  try {
    sessionStorage.removeItem(`${PREFIX}${gameId}`)
  } catch {
    /* ignore */
  }
}

export function mergeResumeIntoConfig(config, stored) {
  if (!stored || stored.game_id !== config.resumeGameId) return config
  return {
    ...config,
    playMode: stored.playMode ?? config.playMode,
    playerCount: stored.playerCount ?? config.playerCount,
    cardId: stored.cardId ?? config.cardId,
    cardId2: stored.cardId2 ?? config.cardId2,
    playerName: stored.playerName ?? config.playerName,
    playerName2: stored.playerName2 ?? config.playerName2,
    minutesRemaining: stored.minutesRemaining ?? config.minutesRemaining,
    minutesRemaining2: stored.minutesRemaining2 ?? config.minutesRemaining2,
    sessionId: stored.sessionId ?? config.sessionId,
    groupId: stored.groupId ?? config.groupId,
    rosterSize: stored.rosterSize ?? config.rosterSize,
    rosterPlayerIds: stored.rosterPlayerIds ?? config.rosterPlayerIds,
    sessionId2: stored.sessionId2 ?? config.sessionId2,
    groupId2: stored.groupId2 ?? config.groupId2,
    rosterSize2: stored.rosterSize2 ?? config.rosterSize2,
    rosterPlayerIds2: stored.rosterPlayerIds2 ?? config.rosterPlayerIds2,
  }
}
