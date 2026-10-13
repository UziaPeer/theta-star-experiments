"""Profile one representative Basic Theta* run before choosing an optimization."""

import cProfile
import pstats
from pathlib import Path

from run import measure

if __name__ == "__main__":
    output = Path(__file__).parent / "thealgorithms_profile"
    output.mkdir(exist_ok=True)
    profiler = cProfile.Profile()
    profiler.runcall(measure, 150, 20, 7, "basic")
    with (output / "profile.txt").open("w", encoding="utf-8") as stream:
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
            "cumtime"
        ).print_stats(25)
