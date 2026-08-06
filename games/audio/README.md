# Hoops audio assets

Canonical paths consumed by `api/audio_manager.py`:

| File | Use |
|------|-----|
| `transition_stinger.mp3` | Level clear + level fail (shared, locked) |
| `bgm_thank_you_not_so_bad.mp3` | Gameplay BGM loop |
| `score_positive.mp3` | Goal / score SFX |
| `score_negative.mp3` | Penalty / miss SFX |
| `countdown_tick.mp3` | Backend countdown 3-2-1 ticks |

**CI / dev placeholders:** short silent clips generated via `ffmpeg` (≈0.15 s).
Replace with production mp3s from the onsite `games/` bundle before hardware deploy.
