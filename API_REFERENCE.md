# API Reference — LED Hoops

Lightweight reference for every FastAPI endpoint in `api/main.py`. Not a
full OpenAPI spec — just enough to understand what this backend exposes at
a glance. Field names below are read directly from `api/main.py` and
`api/models.py`.

---

## Game lifecycle

### `POST /login`
Look up a player by RFID card ID.
- **Body:** `{ card_id: str }`
- **Response:** `{ success: bool, player?: { custom_id, name, phone, time_left (sec), card_id }, error?: str }`

### `POST /start-game`
Create and start a new game instance (kiosk model — clears any prior game
first).
- **Body:** `{ card_id: str, level: int|str, difficulty: "easy"|"normal"|"hard", player_count: int = 1 }` (2 = `.ledb` DK levels only)
- **Response:** `{ success: bool, game_id?: str, ws_url?: str, error?: str }`

### `WS /game/{game_id}`
Real-time game state stream (~60fps). Server → client: `{ type: "game_state", data: <full state dict> }`. Client → server input channel exists but is currently a stub (`# TODO: Feed input to Play.py`) — actual input goes through `POST /game-input`, not this socket.

### `GET /result/{game_id}`
Get final score/leaderboard after a game ends.
- **Response:** `{ success, score, player_name, time_used, difficulty, leaderboard: [{rank, name, score, timestamp}], error? }`

### `POST /logout`
End a session: stops the game and records its score to the DB.
- **Body:** `{ card_id: str, game_id: str }`
- **Response:** `{ success: bool, error?: str }`

### `POST /game-input`
Player input from the simulator (press/release a hoop cell).
- **Body:** `{ row: int, col: int, type: "press"|"release" = "press", game_id?: str }` — applies to the named game, or the first active game if `game_id` omitted.
- **Response:** `{ success: bool, score: int }`

### `POST /save-score`
Persist a finished game to the leaderboard/scores table.
- **Body key fields:** `card_id, card_id2, multiplayer, level (starting), end_level, score (P1 raw), score2 (P2 raw), final_score (P1 normalized), final_score2 (P2 normalized), life, lives_start, result, time_used, levels_cleared, difficulty, started_at`
- **Response:** `{ success: bool, error?: str }`

### `GET /active-game`
Resume support: returns the currently-running (non-game-over) game, if any, so the frontend can restore the simulator after a page reload instead of restarting login.
- **Response:** `{ success: true, game_id, card_id, level, difficulty, player_count, state }` or `{ success: false }`

### `GET /game-state/{game_id}`
State of one specific game (simulator polls its own game).
- **Response:** `{ success: bool, game_id, state }` or `{ success: false, error }`

### `GET /game-state`
State of the first active game (fallback / legacy single-game poll).
- **Response:** `{ success, game_id, state }` or `{ success: false, error }`

### `GET /levels`
List available Hoops levels, grouped by series/category.
- **Response:** `{ success, levels: [{id, name, path, category, multiplayer, file_type}], categories: {casual: [...], level: [...], dk: [...]}, count }`
  - `casual` = `source/-/*.led` (001-011, 1P), `level` = `source/--/*.led` (14-25, 1P), `dk` = `source/---/*.ledb` (DK01-DK10, 2P)

### `GET /leaderboard/{level}?limit=10`
Top scores for one level.
- **Response:** `{ success: true, level: str, entries: [...] }` (entries per `db.get_leaderboard`)

---

## RFID / settings

### `GET /game-settings`
Load hardware/grid/timeout settings from the `led_parameter` shelve (falls back to sane defaults on error).
- **Response:** `{ success, wall_layout, grid_dims: {rows, cols}, timeout_seconds, max_score }`

### `POST /settings`
Runtime overrides **pushed from the central RFID server** (default difficulty, session length). Written to `games/setting/runtime_overrides.json`; does not touch the original read-only shelve config.
- **Body:** `{ default_difficulty?: str, session_minutes?: int }`
- **Response:** `{ success: true, overrides: {...} }`

### `GET /settings`
Read back the current runtime overrides (empty `{}` if none set yet).

---

## Scores / diagnostics

### `GET /scores?since=<ISO timestamp>`
Scores recorded after `since` — used by the RFID server's cross-game leaderboard poller.
- **Response:** `{ success: bool, game: str, scores: [...] }` or `{ success: false, error }`

### `GET /health`
Basic liveness + game-manager stats (`active_games`, `max_games`, `timeout_seconds`).

### `GET /hw-debug`
Live hardware-loop diagnostics: whether `USE_SERIAL_HD` is on, each active game's `running`/`score`/`hw_draw_count`/`last_hw_draw`, and any zombie threads that failed to join during `clear_all()`.
- **Response:** `{ use_serial_hd: bool, active_games: int, games: [...], zombie_threads: [...] }`

---

## Notes

- All endpoints live in `api/main.py`; request/response Pydantic models are in `api/models.py` (note: not every endpoint has a typed model — several, like `/game-input`, `/save-score`, `/settings`, take/return raw `dict`).
- CORS is wide open (`allow_origins=["*"]`) — fine for LAN kiosk use, not for public internet exposure.
- `POST /start-game` calls `game_manager.create_game()`, which internally calls `clear_all()` first — starting a new game always kills any prior game on this machine (single-game-at-a-time kiosk model).
