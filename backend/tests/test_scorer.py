from services.scorer import compute_score


def test_fast_run_earns_speed_bonus():
    assert compute_score(120, 3) == {
        "base_score": 100,
        "speed_bonus": 10,
        "efficiency_penalty": 0,
        "final_score": 110,
    }


def test_slow_run_no_speed_bonus():
    assert compute_score(400, 3)["speed_bonus"] == 0


def test_penalty_two_per_commit_over_twenty():
    assert compute_score(100, 25)["efficiency_penalty"] == 10  # (25-20)*2


def test_final_score_floored_at_zero():
    assert compute_score(400, 100)["final_score"] == 0
