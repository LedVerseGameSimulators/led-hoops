"""Non-blocking AudioManager smoke tests (TESTING_CONTRACT T9)."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.audio_manager import AudioManager


class AudioManagerTests(unittest.TestCase):
    def test_t9_methods_return_without_blocking(self):
        mgr = AudioManager(enabled=False)
        start = time.perf_counter()
        mgr.start_bgm()
        mgr.stop_bgm()
        mgr.play_sfx(mgr.transition_stinger)
        mgr.play_score_positive()
        mgr.play_score_negative()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.05)

    def test_stop_bgm_does_not_call_audio_stop(self):
        mgr = AudioManager(enabled=False)
        mgr._bgm_playing = True
        with mock.patch("api.audio_manager.logger") as log:
            mgr.stop_bgm()
        self.assertFalse(mgr._bgm_playing)


if __name__ == "__main__":
    unittest.main()
