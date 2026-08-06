#!/usr/bin/env python3
"""Bootstrap Hoops transition .led panels under games/source/effects/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.effect_fixtures import (  # noqa: E402
    build_countdown_led,
    build_level_clear_led,
    build_level_fail_led,
)

PROD_EFFECTS_DIR = ROOT / "games" / "source" / "effects"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--effect",
        choices=("countdown", "level_clear", "level_fail"),
        help="Effect to build (default: all)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output .led path (default: games/source/effects/<effect>.led)",
    )
    args = parser.parse_args()

    builders = {
        "countdown": lambda out: build_countdown_led(out, step=1.0),
        "level_clear": lambda out: build_level_clear_led(out, duration=2.5),
        "level_fail": lambda out: build_level_fail_led(out, duration=2.5),
    }
    names = [args.effect] if args.effect else list(builders)
    for name in names:
        out = args.out if args.out and args.effect else PROD_EFFECTS_DIR / f"{name}.led"
        if args.out and not args.effect:
            parser.error("--out requires --effect when building all effects")
        path = builders[name](out)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
