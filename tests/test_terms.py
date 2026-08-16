"""Unit tests for term loading and scanning."""

from pathlib import Path

from git_hygiene.terms import load_patterns, report, scan_text


def write_terms(tmp_path: Path, *terms: str) -> Path:
    path = tmp_path / "deny-terms.txt"
    path.write_text("\n".join(terms) + "\n", encoding="utf-8")
    return path


def test_absent_term_file_yields_no_patterns(tmp_path: Path) -> None:
    assert load_patterns(tmp_path / "nope.txt") == []


def test_comments_and_blanks_ignored(tmp_path: Path) -> None:
    path = write_terms(tmp_path, "# a comment", "", "   ", "realterm")
    assert len(load_patterns(path)) == 1


def test_match_is_case_insensitive(tmp_path: Path) -> None:
    patterns = load_patterns(write_terms(tmp_path, "SomeTerm"))
    assert scan_text("contains someterm here", patterns, "f")
    assert scan_text("contains SOMETERM here", patterns, "f")


def test_word_boundary_prevents_substring_match(tmp_path: Path) -> None:
    """The false-positive class that gets guards switched off: a short
    term must not fire inside an unrelated longer word."""
    patterns = load_patterns(write_terms(tmp_path, "abc"))
    assert not scan_text("xxabcxx and abcdef and zabc", patterns, "f")
    assert scan_text("a bare abc here", patterns, "f")


def test_hyphenated_term_matches(tmp_path: Path) -> None:
    patterns = load_patterns(write_terms(tmp_path, "some-org"))
    assert scan_text("we use some-org daily", patterns, "f")


def test_multi_word_term_matches(tmp_path: Path) -> None:
    patterns = load_patterns(write_terms(tmp_path, "Some Project"))
    assert scan_text("the Some Project repo", patterns, "f")


def test_reports_location_not_term(tmp_path: Path, capsys) -> None:
    patterns = load_patterns(write_terms(tmp_path, "secretname"))
    problems = scan_text("line one\nhas secretname\n", patterns, "somefile.md")
    assert problems == ["  somefile.md:2"]

    rc = report(problems, "staged content")
    captured = capsys.readouterr()
    assert rc == 1
    # The whole point: the term must never reach any output stream.
    assert "secretname" not in captured.err
    assert "secretname" not in captured.out
    assert "somefile.md:2" in captured.err


def test_report_returns_zero_when_clean() -> None:
    assert report([], "staged content") == 0


def test_line_reported_once_even_with_several_terms(tmp_path: Path) -> None:
    patterns = load_patterns(write_terms(tmp_path, "alpha", "beta"))
    assert scan_text("alpha and beta together", patterns, "f") == ["  f:1"]
