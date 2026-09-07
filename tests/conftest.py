"""Headless pytest defaults for Hoops."""
from __future__ import annotations

import os

os.environ.setdefault("HOOPS_AUDIO_DISABLED", "1")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
