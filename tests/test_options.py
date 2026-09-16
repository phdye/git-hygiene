"""Settings reach the resolver from the environment as well as the
command line, and the command line wins.

Driven through check_identifiers.main against real repositories, so a
setting that parses but never reaches resolution fails here. Kept
3.6.8-clean like the rest of tests/.
"""

import subprocess
from pathlib import Path  # noqa: F401 - resolves the type comments below, not dead

import pytest

from git_hygiene import audit_tree, check_identifiers


def git(*args, cwd):
    # type: (str, Path) -> subprocess.CompletedProcess[str]
    return subprocess.run(  # noqa: UP022
        ["git"] + list(args),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        check=False,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> Path
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg-here"))
    for var in (
        "GIT_DENY_TERMS",
        "GIT_HYGIENE_NO_INHERIT",
        "GIT_HYGIENE_NO_WALK",
        "GIT_HYGIENE_WALK_TO",
        "GIT_HYGIENE_SHOW_PRIVATE_TERMS",
    ):
        monkeypatch.delenv(var, raising=False)
    r = tmp_path / "outer" / "repo"
    r.mkdir(parents=True)
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    git("config", "commit.gpgsign", "false", cwd=r)
    monkeypatch.chdir(str(r))
    return r


def stage(repo, text):
    # type: (Path, str) -> None
    (repo / "f.md").write_text(text, encoding="utf-8")
    git("add", "f.md", cwd=repo)


@pytest.fixture
def private_list(tmp_path, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> Path
    path = tmp_path / "private.txt"
    path.write_text("secretword\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DENY_TERMS", str(path))
    return path


def test_show_private_terms_from_environment(repo, private_list, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, pytest.CaptureFixture[str]) -> None
    stage(repo, "a secretword here\n")
    monkeypatch.setenv("GIT_HYGIENE_SHOW_PRIVATE_TERMS", "1")
    assert check_identifiers.main(["--staged"]) == 1
    assert "[secretword]" in capsys.readouterr().err


def test_command_line_turns_the_environment_back_off(repo, private_list, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, pytest.CaptureFixture[str]) -> None
    stage(repo, "a secretword here\n")
    monkeypatch.setenv("GIT_HYGIENE_SHOW_PRIVATE_TERMS", "yes")
    assert check_identifiers.main(["--staged", "--no-show-private-terms"]) == 1
    err = capsys.readouterr().err
    assert "BLOCKED" in err
    assert "secretword" not in err


def test_private_term_withheld_when_environment_says_off(repo, private_list, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, pytest.CaptureFixture[str]) -> None
    stage(repo, "a secretword here\n")
    monkeypatch.setenv("GIT_HYGIENE_SHOW_PRIVATE_TERMS", "0")
    assert check_identifiers.main(["--staged"]) == 1
    assert "secretword" not in capsys.readouterr().err


def test_malformed_boolean_is_a_usage_error(repo, private_list, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, pytest.CaptureFixture[str]) -> None
    stage(repo, "clean\n")
    monkeypatch.setenv("GIT_HYGIENE_NO_WALK", "maybe")
    with pytest.raises(SystemExit) as exc:
        check_identifiers.main(["--staged"])
    assert exc.value.code == 2
    assert "GIT_HYGIENE_NO_WALK" in capsys.readouterr().err


def test_no_walk_and_walk_to_from_environment(repo, tmp_path, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    # A list in the repository's parent is found only by the walk.
    (repo.parent / ".deny-terms.private").write_text("walkedword\n", encoding="utf-8")
    stage(repo, "walkedword\n")
    monkeypatch.setenv("GIT_HYGIENE_WALK_TO", str(tmp_path))
    assert check_identifiers.main(["--staged"]) == 1
    monkeypatch.setenv("GIT_HYGIENE_NO_WALK", "true")
    assert check_identifiers.main(["--staged"]) == 0
    assert check_identifiers.main(["--staged", "--walk"]) == 1


def test_no_inherit_from_environment(repo, private_list, monkeypatch):
    # type: (Path, Path, pytest.MonkeyPatch) -> None
    (repo / ".deny-terms").write_text("# git-hygiene: public\nteamword\n", encoding="utf-8")
    stage(repo, "teamword\n")
    assert check_identifiers.main(["--staged"]) == 1
    monkeypatch.setenv("GIT_HYGIENE_NO_INHERIT", "on")
    assert check_identifiers.main(["--staged"]) == 0
    assert check_identifiers.main(["--staged", "--inherit"]) == 1


def test_explain_never_names_a_refused_private_term(repo, tmp_path, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, pytest.CaptureFixture[str]) -> None
    private = tmp_path / "private.txt"
    private.write_text("secretword\n", encoding="utf-8")
    public = tmp_path / "public.txt"
    public.write_text("# git-hygiene: public\n!secretword\n", encoding="utf-8")
    monkeypatch.setenv("GIT_HYGIENE_SHOW_PRIVATE_TERMS", "1")
    args = ["--terms", str(private), "--terms", str(public)]
    assert check_identifiers.main(["--staged", "--explain"] + args) == 1
    err = capsys.readouterr().err
    assert "unauthorized negation" in err
    assert "secretword" not in err
    assert audit_tree.main([str(repo), "--explain"] + args) == 1
    err = capsys.readouterr().err
    assert "unauthorized negation" in err
    assert "secretword" not in err


def test_refused_negation_blocks_the_commit_check(repo, tmp_path, capsys):
    # type: (Path, Path, pytest.CaptureFixture[str]) -> None
    private = tmp_path / "private.txt"
    private.write_text("secretword\n", encoding="utf-8")
    public = tmp_path / "public.txt"
    public.write_text("# git-hygiene: public\n!secretword\n", encoding="utf-8")
    stage(repo, "clean content\n")
    rc = check_identifiers.main(["--staged", "--terms", str(private), "--terms", str(public)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "BLOCKED: term resolution failed" in err
    assert "secretword" not in err
