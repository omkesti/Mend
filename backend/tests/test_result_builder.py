import datetime

from services.result_builder import build_results


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _state(**kw) -> dict:
    base = {
        "run_id": "r", "repo_url": "u", "team_name": "T", "leader_name": "L",
        "branch_name": "B", "detected_stack": "python", "workspace_path": ".",
        "fixes": [], "ci_results": [],
    }
    base.update(kw)
    return base


def test_passed_run_is_scored():
    r = build_results(_state(all_tests_passing=True, error=None), _now())
    assert r["status"] == "passed"
    assert r["score"]["final_score"] == 110


def test_failed_run_scores_zero():
    r = build_results(_state(all_tests_passing=False, error="no tests"), _now())
    assert r["status"] == "failed"
    assert r["score"]["final_score"] == 0


def test_fixes_serialized_with_file_key():
    fixes = [{"file_path": "backend/calc.py", "bug_type": "LOGIC", "line_number": 1,
              "commit_message": "m", "description": "d", "status": "fixed", "patch": "p"}]
    r = build_results(_state(all_tests_passing=True, error=None, fixes=fixes), _now())
    assert r["fixes"][0]["file"] == "backend/calc.py"
    assert "file_path" not in r["fixes"][0]
    assert r["total_fixes_applied"] == 1
