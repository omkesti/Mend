"""Scoring — pure functions, no IO.

base 100; +10 speed bonus when the run finishes under 5 minutes; -2 per commit
over 20; final score floored at 0.
"""

from __future__ import annotations

BASE_SCORE = 100
SPEED_BONUS = 10
SPEED_THRESHOLD_SECONDS = 300
COMMIT_FREE_ALLOWANCE = 20
PENALTY_PER_COMMIT = 2


def compute_score(duration_seconds: float, total_commits: int) -> dict:
    """Return the score breakdown for a completed run."""
    speed_bonus = SPEED_BONUS if duration_seconds < SPEED_THRESHOLD_SECONDS else 0
    efficiency_penalty = max(0, total_commits - COMMIT_FREE_ALLOWANCE) * PENALTY_PER_COMMIT
    final_score = max(0, BASE_SCORE + speed_bonus - efficiency_penalty)

    return {
        "base_score": BASE_SCORE,
        "speed_bonus": speed_bonus,
        "efficiency_penalty": efficiency_penalty,
        "final_score": final_score,
    }
