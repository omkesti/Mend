import pytest

from agent.tools.github import build_branch_name, parse_repo_url


@pytest.mark.parametrize("url", [
    "https://github.com/omkesti/Mend",
    "https://github.com/omkesti/Mend.git",
    "https://github.com/omkesti/Mend/",
    "git@github.com:omkesti/Mend.git",
])
def test_parse_repo_url_variants(url):
    assert parse_repo_url(url) == ("omkesti", "Mend")


def test_parse_repo_url_rejects_garbage():
    with pytest.raises(ValueError):
        parse_repo_url("not-a-url")


def test_build_branch_name_matches_spec():
    assert build_branch_name("RIFT ORGANISERS", "Saiyam Kumar") == "RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix"
    assert build_branch_name("Code Warriors", "John Doe") == "CODE_WARRIORS_JOHN_DOE_AI_Fix"
