"""A term file's class comes from its name or location
(doc/proposal/2026-09-16.filename-authoritative-term-classes.md).

Cases A to D are the proposal's reproductions, each driven through
`check-identifiers --staged` against a real repository. Every refusal is
asserted on its message as well as its exit code, since a crashed run
and a refusing run share a code.

Kept 3.6.8-clean like the rest of tests/.
"""

import subprocess
from pathlib import Path  # noqa: F401 - resolves the type comments below

import pytest

from git_hygiene import audit_tree, check_identifiers, resolution

SECRET = "zqvprivateword"  # noqa: S105 - a planted term, not a credential
TEAM = "zqvteamword"


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
    for name in (
        "GIT_DENY_TERMS",
        "GIT_HYGIENE_NO_INHERIT",
        "GIT_HYGIENE_NO_WALK",
        "GIT_HYGIENE_WALK_TO",
        "GIT_HYGIENE_SHOW_PRIVATE_TERMS",
        "GIT_HYGIENE_EXIT_CONTRACT",
    ):
        monkeypatch.delenv(name, raising=False)
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "test@example.invalid", cwd=r)
    git("config", "user.name", "Test", cwd=r)
    git("config", "commit.gpgsign", "false", cwd=r)
    monkeypatch.chdir(str(r))
    return r


def write(path, text):
    # type: (Path, str) -> Path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def staged(*argv):
    # type: (str) -> int
    return check_identifiers.main(["--staged", "--no-walk"] + list(argv))


def test_a_tracked_undeclared_team_list_commits_cleanly(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", TEAM + "\n")
    git("add", ".deny-terms", cwd=repo)
    assert staged() == 0
    out, err = capsys.readouterr()
    assert "tracked private" not in err
    assert err == ""


def test_a_team_list_still_enforces_and_prints_its_terms(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", TEAM + "\n")
    git("add", ".deny-terms", cwd=repo)
    git("commit", "-q", "-m", "team list", cwd=repo)
    write(repo / "doc.md", "mentions " + TEAM + "\n")
    git("add", "doc.md", cwd=repo)
    assert staged() == 1
    err = capsys.readouterr()[1]
    assert "BLOCKED: staged content" in err
    assert "doc.md:1  [" + TEAM + "]" in err


def test_b_a_declared_public_list_does_not_flag_itself(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", "# git-hygiene: public\n" + TEAM + "\n")
    git("add", ".deny-terms", cwd=repo)
    assert staged() == 0
    out, err = capsys.readouterr()
    assert "BLOCKED" not in err
    assert err == ""


def test_c_a_root_private_list_is_loaded_and_enforced(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms.private", SECRET + "\n")
    write(repo / "doc.md", "mentions " + SECRET + "\n")
    git("add", "doc.md", cwd=repo)
    assert staged() == 1
    out, err = capsys.readouterr()
    assert "BLOCKED: staged content" in err
    assert "doc.md:1" in err
    assert SECRET not in out + err


def test_c_a_tracked_root_private_list_is_fatal(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms.private", SECRET + "\n")
    git("add", "-f", ".deny-terms.private", cwd=repo)
    assert staged() == 1
    out, err = capsys.readouterr()
    assert "tracked private term file" in err
    assert ".deny-terms.private" in err
    assert SECRET not in out + err


def test_d_a_team_list_declaring_private_is_refused(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", "# git-hygiene: private\n" + TEAM + "\n")
    git("add", ".deny-terms", cwd=repo)
    assert staged() == 1
    err = capsys.readouterr()[1]
    assert "BLOCKED: term resolution failed" in err
    assert "declares itself private, but its name or location makes it public" in err
    assert TEAM not in err


def test_a_private_name_declaring_public_is_an_error_naming_both_claims(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms.private", "# git-hygiene: public\n" + SECRET + "\n")
    assert staged() == 1
    out, err = capsys.readouterr()
    assert ".deny-terms.private: declares itself public" in err
    assert "makes it private" in err
    assert SECRET not in out + err


def test_a_location_private_file_declaring_public_is_an_error(repo, tmp_path, monkeypatch, capsys):
    # type: (Path, Path, pytest.MonkeyPatch, object) -> None
    xdg = tmp_path / "xdg"
    write(xdg / "git" / "deny-terms.txt", "# git-hygiene: public\n" + SECRET + "\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert staged() == 1
    assert (
        "declares itself public, but its name or location makes it private"
        in (capsys.readouterr()[1])
    )


def test_an_unrecognized_named_file_is_private(repo, capsys):
    # type: (Path, object) -> None
    terms = write(repo / "list.txt", SECRET + "\n")
    result = resolution.resolve(anchor=repo, extra_terms=[str(terms)], no_walk=True)
    assert [s.klass for s in result.loaded()] == ["private"]
    write(repo / "doc.md", SECRET + "\n")
    git("add", "doc.md", cwd=repo)
    assert staged("--terms", str(terms)) == 1
    out, err = capsys.readouterr()
    assert "doc.md:1" in err
    assert SECRET not in out + err


def test_an_unrecognized_named_file_that_is_tracked_is_fatal(repo, capsys):
    # type: (Path, object) -> None
    terms = write(repo / "sub" / "list.txt", SECRET + "\n")
    git("add", "sub/list.txt", cwd=repo)
    assert staged("--terms", str(terms)) == 1
    assert "tracked private term file" in capsys.readouterr()[1]


def test_a_named_dot_deny_terms_is_public(repo):
    # type: (Path) -> None
    terms = write(repo / "shared" / ".deny-terms", TEAM + "\n")
    result = resolution.resolve(anchor=repo, extra_terms=[str(terms)], no_walk=True)
    assert result.patterns[0].klass == "public"
    assert not result.fatal


def _team_list_carrying_a_private_term(repo):
    # type: (Path) -> None
    write(repo / ".git" / "info" / "deny-terms", SECRET + "\n")
    write(repo / ".deny-terms", TEAM + "\n" + SECRET + "\n")
    git("add", ".deny-terms", cwd=repo)


def test_a_team_list_carrying_a_private_term_is_refused_without_naming_it(repo, capsys):
    # type: (Path, object) -> None
    _team_list_carrying_a_private_term(repo)
    assert staged() == 1
    out, err = capsys.readouterr()
    assert "BLOCKED: staged content" in err
    assert ".deny-terms:2" in err
    assert ".deny-terms:1" not in err  # its own public entry is not a finding
    assert SECRET not in out
    assert SECRET not in err


def test_the_private_term_is_named_only_when_asked(repo, capsys):
    # type: (Path, object) -> None
    _team_list_carrying_a_private_term(repo)
    assert staged("--show-private-terms") == 1
    err = capsys.readouterr()[1]
    assert ".deny-terms:2  [" + SECRET + "]" in err


def test_the_same_holds_when_the_team_list_is_the_first_to_introduce_it(repo, capsys):
    # type: (Path, object) -> None
    """Provenance goes to the first contributor. A private list named
    later still has to catch the term in the team list."""
    later = write(repo.parent / "later.txt", SECRET + "\n")
    write(repo / ".deny-terms", SECRET + "\n")
    git("add", ".deny-terms", cwd=repo)
    assert staged("--terms", str(later)) == 1
    out, err = capsys.readouterr()
    assert ".deny-terms:1" in err
    assert SECRET not in out + err


def test_explain_shows_the_derived_class_of_every_candidate(repo, capsys):
    # type: (Path, object) -> None
    assert check_identifiers.main(["--staged", "--no-walk", "--explain"]) == 0
    rows = {}
    for line in capsys.readouterr()[0].splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 4:
            rows[fields[-4]] = fields[-3]
    by_name = {Path(k).name: v for k, v in rows.items()}
    assert by_name[".deny-terms"] == "public"
    assert by_name[".deny-terms.private"] == "private"
    assert by_name["deny-terms.txt"] == "private"
    assert by_name["deny-terms"] == "private"


def test_a_public_list_cannot_cancel_a_term_a_private_list_also_holds(repo):
    # type: (Path) -> None
    first = write(repo / "a" / ".deny-terms", "alpha\n")
    private = write(repo / "b.txt", "alpha\n")
    negating = write(repo / "c" / ".deny-terms", "!alpha\n")
    result = resolution.resolve(
        anchor=repo, extra_terms=[str(first), str(private), str(negating)], no_walk=True
    )
    assert result.fatal
    assert any("unauthorized negation" in e and "b.txt" in e for e in result.errors)
    assert {p.term for p in result.patterns} == {"alpha"}


def test_audit_does_not_flag_a_committed_team_list(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", TEAM + "\n")
    git("add", ".deny-terms", cwd=repo)
    git("commit", "-q", "-m", "team list", cwd=repo)
    write(repo / ".deny-terms", TEAM + "\nzqvsecondword\n")
    git("commit", "-q", "-am", "grow the list", cwd=repo)
    assert audit_tree.main([str(repo), "--no-walk"]) == 0
    assert audit_tree.main([str(repo), "--no-walk", "--objects"]) == 0
    assert "CLEAN" in capsys.readouterr()[0]


def test_audit_finds_a_private_term_in_an_old_version_of_the_team_list(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", TEAM + "\n" + SECRET + "\n")
    git("add", ".deny-terms", cwd=repo)
    git("commit", "-q", "-m", "team list", cwd=repo)
    write(repo / ".deny-terms", TEAM + "\n")
    git("commit", "-q", "-am", "drop a line", cwd=repo)
    write(repo / ".git" / "info" / "deny-terms", SECRET + "\n")
    assert audit_tree.main([str(repo), "--no-walk"]) == 0
    assert audit_tree.main([str(repo), "--no-walk", "--objects"]) == 1
    out, err = capsys.readouterr()
    assert "FAIL - identifiers present" in err
    assert SECRET not in out + err


# --- exit contract 2 -------------------------------------------------------


def test_contract_2_binary_only_commit_is_not_applicable(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".git" / "info" / "deny-terms", SECRET + "\n")
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02" + SECRET.encode("ascii"))
    git("add", "blob.bin", cwd=repo)
    assert staged("--exit-contract", "2") == 1  # binaries are still scanned
    capsys.readouterr()
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02 nothing here")
    git("add", "blob.bin", cwd=repo)
    assert staged("--exit-contract", "2") == 3
    assert staged() == 0  # contract 1 is unchanged


def test_contract_2_without_a_private_source_could_not_run(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".deny-terms", TEAM + "\n")
    write(repo / "doc.md", "ordinary\n")
    git("add", "doc.md", cwd=repo)
    assert staged("--exit-contract", "2") == 4
    err = capsys.readouterr()[1]
    assert "no private term source resolved" in err
    assert "deny-terms.txt" in err
    assert TEAM not in err
    assert staged() == 0


def test_contract_2_reads_the_environment(repo, monkeypatch):
    # type: (Path, pytest.MonkeyPatch) -> None
    write(repo / "doc.md", "ordinary\n")
    git("add", "doc.md", cwd=repo)
    monkeypatch.setenv("GIT_HYGIENE_EXIT_CONTRACT", "2")
    assert staged() == 4
    assert staged("--exit-contract", "1") == 0
    monkeypatch.setenv("GIT_HYGIENE_EXIT_CONTRACT", "3")
    with pytest.raises(SystemExit) as info:
        staged()
    assert info.value.code == 2


def test_contract_2_message_file_missing_could_not_run(repo, capsys):
    # type: (Path, object) -> None
    write(repo / ".git" / "info" / "deny-terms", SECRET + "\n")
    missing = str(repo / "no-such-message")
    assert check_identifiers.main(["--message", missing, "--exit-contract", "2"]) == 4
    assert "commit message file not found" in capsys.readouterr()[1]
    assert check_identifiers.main(["--message", missing]) == 0
