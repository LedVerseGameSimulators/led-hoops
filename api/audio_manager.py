"""Non-blocking audio for Hoops marathon effects and gameplay."""
from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from .config import GAMES_ROOT


class AudioManager:
    """Fire-and-forget SFX/BGM — never block the game thread on mixer."""

    def __init__(self, settings=None, *, enabled: bool = True):
        self._enabled = enabled
        self._bgm_playing = False
        audio_dir = Path(GAMES_ROOT) / "audio"
        self._bgm_path = str(audio_dir / "bgm_thank_you_not_so_bad.mp3")
        self._score_pos = str(audio_dir / "score_positive.mp3")
        self._score_neg = str(audio_dir / "score_negative.mp3")
        self.tick_sfx = str(audio_dir / "countdown_tick.mp3")
        self.transition_stinger = str(audio_dir / "transition_stinger.mp3")
        if enabled:
            try:
                from audio_play.audio import Audio

                Audio().init()
            except Exception as exc:
                logger.warning(f"AudioManager init skipped: {exc}")
                self._enabled = False

    def start_bgm(self) -> None:
        if not self._enabled or self._bgm_playing:
            return
        if not os.path.isfile(self._bgm_path):
            return
        try:
            from audio_play.audio import Audio

            Audio().play_bmg(self._bgm_path, loops=-1)
            self._bgm_playing = True
        except Exception as exc:
            logger.warning(f"BGM start failed: {exc}")

    def stop_bgm(self) -> None:
        if not self._bgm_playing:
            return
        try:
            from pygame import mixer

            mixer.music.stop()
            mixer.music.unload()
        except Exception:
            pass
        self._bgm_playing = False

    def play_sfx(self, path: str | None) -> None:
        if not self._enabled or not path or not os.path.isfile(path):
            return
        try:
            from audio_play.audio import Audio

            Audio().play(path)
        except Exception as exc:
            logger.warning(f"SFX play failed ({path}): {exc}")

    def play_score_positive(self) -> None:
        self.play_sfx(self._score_pos)

    def play_score_negative(self) -> None:
        self.play_sfx(self._score_neg)
