"""Non-blocking audio for Hoops marathon effects and gameplay."""
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path

from loguru import logger

from .config import GAMES_ROOT

_CMD_STOP_BGM = "stop_bgm"
_CMD_START_BGM = "start_bgm"
_CMD_PLAY_SFX = "play_sfx"
_CMD_SHUTDOWN = "shutdown"


class AudioManager:
    """Fire-and-forget SFX/BGM on a daemon worker — game thread never waits on mixer."""

    def __init__(self, settings=None, *, enabled: bool = True):
        # Explicit kill-switch for CI / headless (HOOPS_AUDIO_DISABLED=1).
        if os.environ.get("HOOPS_AUDIO_DISABLED", "0") == "1":
            enabled = False
        self._enabled = enabled
        self._bgm_playing = False
        self._mixer = None
        self._queue: queue.Queue = queue.Queue(maxsize=256)
        self._thread: threading.Thread | None = None
        self._worker_started = False

        audio_dir = Path(GAMES_ROOT) / "audio"
        self._bgm_path = str(audio_dir / "bgm_thank_you_not_so_bad.mp3")
        self._score_pos = str(audio_dir / "score_positive.mp3")
        self._score_neg = str(audio_dir / "score_negative.mp3")
        self.tick_sfx = str(audio_dir / "countdown_tick.mp3")
        self.transition_stinger = str(audio_dir / "transition_stinger.mp3")

        if enabled:
            self._start_worker()

    def _start_worker(self) -> None:
        if self._worker_started:
            return
        self._worker_started = True
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._mixer = pygame.mixer
        except Exception as exc:
            logger.warning(f"AudioManager init skipped: {exc}")
            self._enabled = False
            return
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="hoops-audio"
        )
        self._thread.start()

    def _worker(self) -> None:
        while True:
            try:
                cmd, payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if cmd == _CMD_SHUTDOWN:
                break
            if not self._mixer:
                continue
            try:
                if cmd == _CMD_STOP_BGM:
                    self._stop_bgm_locked()
                elif cmd == _CMD_START_BGM:
                    path = payload
                    if path and os.path.isfile(path):
                        self._mixer.music.load(path)
                        self._mixer.music.play(loops=-1)
                        self._bgm_playing = True
                elif cmd == _CMD_PLAY_SFX:
                    path = payload
                    if path and os.path.isfile(path):
                        ch = self._mixer.find_channel(True)
                        if ch:
                            ch.play(self._mixer.Sound(path))
            except Exception as exc:
                logger.warning(f"Audio worker error ({cmd}): {exc}")

    def _stop_bgm_locked(self) -> None:
        self._bgm_playing = False
        try:
            self._mixer.music.stop()
            try:
                self._mixer.music.unload()
            except Exception:
                pass
        except Exception:
            pass

    def _put(self, cmd: str, payload=None) -> None:
        if not self._enabled:
            return
        try:
            self._queue.put_nowait((cmd, payload))
        except queue.Full:
            pass

    def start_bgm(self) -> None:
        if not self._enabled or self._bgm_playing:
            return
        if not os.path.isfile(self._bgm_path):
            return
        self._bgm_playing = True
        self._put(_CMD_START_BGM, self._bgm_path)

    def stop_bgm(self) -> None:
        if not self._bgm_playing:
            return
        self._bgm_playing = False
        if not self._enabled:
            return
        self._put(_CMD_STOP_BGM)

    def play_sfx(self, path: str | None) -> None:
        if not self._enabled or not path:
            return
        self._put(_CMD_PLAY_SFX, path)

    def play_score_positive(self) -> None:
        self.play_sfx(self._score_pos)

    def play_score_negative(self) -> None:
        self.play_sfx(self._score_neg)

    def shutdown(self) -> None:
        if self._thread and self._thread.is_alive():
            self._put(_CMD_SHUTDOWN)
            self._thread.join(timeout=1.0)
