import json

from agent.tools.stack_detector import detect_projects


def _mk(tmp_path, files: dict) -> str:
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return str(tmp_path)


def test_python_at_root(tmp_path):
    ws = _mk(tmp_path, {"requirements.txt": "pytest\n", "test_x.py": "def test(): pass"})
    projects = detect_projects(ws)
    assert len(projects) == 1
    assert projects[0]["stack"] == "python"
    assert projects[0]["project_dir"] == ""
    assert projects[0]["test_command"] == "pytest --tb=short -v"


def test_monorepo_detects_both_stacks(tmp_path):
    ws = _mk(tmp_path, {
        "backend/requirements.txt": "pytest\n",
        "backend/test_a.py": "def test(): pass",
        "frontend/package.json": json.dumps({"scripts": {"test": "vitest"}}),
        "frontend/a.test.js": "x",
    })
    by_stack = {p["stack"]: p for p in detect_projects(ws)}
    assert set(by_stack) == {"python", "node"}
    assert by_stack["python"]["project_dir"] == "backend"
    assert by_stack["node"]["project_dir"] == "frontend"


def test_unknown_repo_has_no_projects(tmp_path):
    assert detect_projects(_mk(tmp_path, {"README.md": "x"})) == []


def test_aggregate_root_manifest_is_shadowed(tmp_path):
    # A root requirements.txt that just re-exports backend/ must not become its
    # own (un-runnable) project; only the real backend project should remain.
    ws = _mk(tmp_path, {
        "requirements.txt": "-r backend/requirements.txt\n",
        "backend/requirements.txt": "pytest\n",
        "backend/test_a.py": "def test(): pass",
    })
    projects = detect_projects(ws)
    assert len(projects) == 1
    assert projects[0]["project_dir"] == "backend"
