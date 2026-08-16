"""Unit tests for the low-level primitives in git_hygiene.terms:
compiling a term, scanning text against compiled patterns, and
deciding what a report may print. Layered resolution itself - which
files get read, classification, negation - is tested in
test_resolution.py; this file stays beneath that, matching the module
boundary described in terms.py's own docstring.
"""

from pathlib import Path

from git_hygiene.terms import compile_term, report, scan_text


def pub(term):
    # type: (str) -> object
    return compile_term(term, Path("team.deny-terms"), "public")


def priv(term):
    # type: (str) -> object
    return compile_term(term, Path("~/.config/git/deny-terms.txt"), "private")


def test_match_is_case_insensitive():
    # type: () -> None
    hits = scan_text("contains SomeTerm here", [priv("someterm")], "f")
    assert len(hits) == 1


def test_word_boundary_prevents_substring_match():
    # type: () -> None
    """The false-positive class that gets guards switched off: a short
    term must not fire inside an unrelated longer word."""
    patterns = [priv("abc")]
    assert not scan_text("xxabcxx and abcdef and zabc", patterns, "f")
    assert scan_text("a bare abc here", patterns, "f")


def test_hyphenated_term_matches():
    # type: () -> None
    assert scan_text("we use some-org daily", [priv("some-org")], "f")


def test_multi_word_term_matches():
    # type: () -> None
    assert scan_text("the Some Project repo", [priv("Some Project")], "f")


def test_line_reported_once_even_with_several_terms():
    # type: () -> None
    hits = scan_text("alpha and beta together", [priv("alpha"), priv("beta")], "f")
    assert [h.location for h in hits] == ["f:1"]


def test_hit_carries_line_and_source():
    # type: () -> None
    hits = scan_text("line one\nhas secretname\n", [priv("secretname")], "somefile.md")
    assert len(hits) == 1
    assert hits[0].location == "somefile.md:2"
    assert hits[0].term == "secretname"
    assert hits[0].klass == "private"


def test_report_returns_zero_when_clean():
    # type: () -> None
    assert report([], "staged content") == 0


def test_private_term_never_reaches_output_by_default(capsys):
    # type: (object) -> None
    hits = scan_text("has secretname\n", [priv("secretname")], "somefile.md")
    rc = report(hits, "staged content")
    captured = capsys.readouterr()
    assert rc == 1
    assert "secretname" not in captured.err
    assert "secretname" not in captured.out
    assert "somefile.md:1" in captured.err


def test_show_private_terms_reveals_it(capsys):
    # type: (object) -> None
    hits = scan_text("has secretname\n", [priv("secretname")], "somefile.md")
    rc = report(hits, "staged content", show_private=True)
    captured = capsys.readouterr()
    assert rc == 1
    assert "secretname" in captured.err


def test_public_term_prints_by_default(capsys):
    # type: (object) -> None
    hits = scan_text("has teamword\n", [pub("teamword")], "somefile.md")
    rc = report(hits, "staged content")
    captured = capsys.readouterr()
    assert rc == 1
    assert "teamword" in captured.err


def test_no_show_terms_hides_even_public(capsys):
    # type: (object) -> None
    hits = scan_text("has teamword\n", [pub("teamword")], "somefile.md")
    rc = report(hits, "staged content", show_terms=False)
    captured = capsys.readouterr()
    assert rc == 1
    assert "teamword" not in captured.err
    assert "somefile.md:1" in captured.err
