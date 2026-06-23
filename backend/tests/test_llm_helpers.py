from agent.llm import clamp_bug_type, strip_code_fences


def test_clamp_keeps_valid_type():
    assert clamp_bug_type("SYNTAX") == "SYNTAX"


def test_clamp_uppercases():
    assert clamp_bug_type("import") == "IMPORT"


def test_clamp_falls_back_to_linting():
    assert clamp_bug_type("NONSENSE") == "LINTING"
    assert clamp_bug_type(None) == "LINTING"


def test_strip_code_fences():
    assert strip_code_fences("```json\n[1, 2]\n```") == "[1, 2]"
    assert strip_code_fences("```\n{}\n```") == "{}"
    assert strip_code_fences("[1, 2]") == "[1, 2]"
