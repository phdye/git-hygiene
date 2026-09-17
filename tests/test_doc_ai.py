"""Hold doc/ai/, the usage documentation for sessions in other
repositories, to its required structure and to the code it describes.

The structure gate runs the external checker (`ai-docs-check`) and skips,
naming why, when that checker is not available. The interface gate always
runs: the console scripts, each command's options, the environment
variables and the hook ids listed in doc/ai/ must equal what the code and
the manifest define. A list that drifts from the code misleads exactly
the reader who cannot check the source.

Kept 3.6.8-clean like the rest of tests/.
"""

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from git_hygiene import options

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_AI = REPO_ROOT / "doc" / "ai"
CLI = DOC_AI / "cli"
COMMANDS = CLI / "command"
SHARED_OPTIONS_PAGE = CLI / "resolution-options.md"
ENVIRONMENT_PAGE = CLI / "environment.md"
HOOKS_PAGE = CLI / "hooks.md"

SPELLING = re.compile(r"`([^`]+)`")
OPTION = re.compile(r"^--?[A-Za-z0-9][A-Za-z0-9-]*$")
CONSOLE_SCRIPT = re.compile(r"^\s+([A-Za-z0-9_-]+)\s*=\s*([A-Za-z0-9_.]+):([A-Za-z0-9_]+)\s*$")
ENV_NAME = re.compile(r"\b(GIT_HYGIENE_[A-Z_]+|GIT_DENY_TERMS)\b")
ENV_LITERAL = re.compile(r"""os\.environ(?:\.get\(|\[)\s*["']([A-Z][A-Z0-9_]*)["']""")
ANNEX_PATH = re.compile(r"(^|[\s(`])a/[a-z]", re.MULTILINE)


def rel(path):
    # type: (Path) -> str
    return path.relative_to(REPO_ROOT).as_posix()


# --- structure ---------------------------------------------------------------


def find_checker():
    # type: () -> str
    return os.environ.get("AI_DOCS_CHECK") or shutil.which("ai-docs-check") or ""


def test_structure_passes_ai_docs_check():
    # type: () -> None
    checker = find_checker()
    if not checker:
        pytest.skip(
            "ai-docs-check not found: set AI_DOCS_CHECK to the path of my-standards'"
            " bin/ai-docs-check, or put ai-docs-check on PATH"
        )
    r = subprocess.run(  # noqa: S603, UP022
        [sys.executable, checker, str(DOC_AI)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # noqa: UP021 - text= is also 3.7+ only
        check=False,
    )
    assert r.returncode == 0, (
        f"doc/ai/ fails ai-docs-check (exit {r.returncode}). Fix each finding below in the"
        " named page; for a stale route table, edit the page's 'Read when:' line"
        f" and run `ai-docs-check --write doc/ai`.\n{r.stdout}{r.stderr}"
    )


# --- reading the pages -------------------------------------------------------


def table_column(page, header):
    # type: (Path, str) -> list
    """The first-column cells of every table on `page` whose first header
    cell is `header`."""
    lines = page.read_text(encoding="utf-8").splitlines()
    cells = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        first = line.strip("|").split("|")[0].strip() if line.startswith("|") else None
        if first == header and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells.append(lines[i].strip().strip("|").split("|")[0].strip())
                i += 1
            continue
        i += 1
    return cells


def spellings(page, header, shape=None):
    # type: (Path, str, object) -> set
    """Backticked names in the first column of `header` tables. A spelling
    may carry a metavar after a space (`--terms FILE`); only the name
    counts."""
    found = set()
    for cell in table_column(page, header):
        for text in SPELLING.findall(cell):
            name = text.split()[0]
            if shape is None or shape.match(name):
                found.add(name)
    return found


# --- the interface definition ------------------------------------------------


def console_scripts():
    # type: () -> dict
    """name -> (module, function), from setup.cfg's console_scripts."""
    text = (REPO_ROOT / "setup.cfg").read_text(encoding="utf-8")
    section = text.split("console_scripts =", 1)[1]
    scripts = {}
    for line in section.splitlines()[1:]:
        match = CONSOLE_SCRIPT.match(line)
        if not match:
            break
        scripts[match.group(1)] = (match.group(2), match.group(3))
    return scripts


class _CapturedParserError(Exception):
    def __init__(self, parser):
        # type: (argparse.ArgumentParser) -> None
        super().__init__("parser captured")
        self.parser = parser


def captured_parser(module_name, function, monkeypatch):
    # type: (str, str, pytest.MonkeyPatch) -> argparse.ArgumentParser
    """The parser a command's entry point builds, taken at the moment it
    would parse, so main() goes no further and touches nothing."""

    def capture(self, *args, **kwargs):
        # type: (argparse.ArgumentParser, object, object) -> None
        raise _CapturedParserError(self)

    main = getattr(importlib.import_module(module_name), function)
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    monkeypatch.setattr(argparse.ArgumentParser, "parse_known_args", capture)
    try:
        main([])
    except _CapturedParserError as caught:
        return caught.parser
    finally:
        monkeypatch.undo()
    raise AssertionError(
        f"{module_name}.{function} returned without parsing arguments;"
        " tests/test_doc_ai.py cannot read its options. Update captured_parser()"
        " for the new entry point."
    )


def option_strings(parser):
    # type: (argparse.ArgumentParser) -> set
    return {s for action in parser._actions for s in action.option_strings}


def shared_options():
    # type: () -> set
    parser = argparse.ArgumentParser(add_help=False)
    options.add_resolution_options(parser)
    return option_strings(parser)


# --- interface ---------------------------------------------------------------


def test_every_console_script_has_a_command_page():
    # type: () -> None
    pages = {p.stem for p in COMMANDS.glob("*.md") if p.name != "index.md"}
    scripts = set(console_scripts())
    assert scripts, "no console_scripts found in setup.cfg; fix console_scripts() here"
    assert pages == scripts, (
        "doc/ai/cli/command/ must hold one page per console script in setup.cfg."
        f" Add a page for {sorted(scripts - pages)}, remove the page for"
        f" {sorted(pages - scripts)}, and regenerate the route table."
    )


def test_shared_resolution_options_are_documented():
    # type: () -> None
    shared = shared_options()
    documented = spellings(SHARED_OPTIONS_PAGE, "Option", OPTION)
    assert documented == shared, (
        f"The Option table in {rel(SHARED_OPTIONS_PAGE)} must list exactly the options"
        f" git_hygiene/options.py adds. Add rows for {sorted(shared - documented)};"
        f" remove rows for {sorted(documented - shared)}."
    )


@pytest.mark.parametrize("name", sorted(console_scripts()))
def test_each_command_page_lists_its_options(name, monkeypatch):
    # type: (str, pytest.MonkeyPatch) -> None
    module_name, function = console_scripts()[name]
    defined = option_strings(captured_parser(module_name, function, monkeypatch))
    page = COMMANDS / (name + ".md")
    shared = shared_options()
    if shared <= defined:
        defined = defined - shared
        link = "../resolution-options.md"
        assert link in page.read_text(encoding="utf-8"), (
            f"{name} takes the shared resolution options; {rel(page)} must link {link}."
        )
    documented = spellings(page, "Option", OPTION)
    assert documented == defined, (
        f"The Option table in {rel(page)} must list exactly the options"
        f" {module_name} defines (shared resolution options belong on"
        f" {rel(SHARED_OPTIONS_PAGE)} instead). Add rows for {sorted(defined - documented)};"
        f" remove rows for {sorted(documented - defined)}."
    )


def test_environment_page_lists_every_variable_read():
    # type: () -> None
    read = set()
    for source in sorted((REPO_ROOT / "src" / "git_hygiene").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        read |= set(ENV_NAME.findall(text)) | set(ENV_LITERAL.findall(text))
    documented = spellings(ENVIRONMENT_PAGE, "Variable")
    assert documented == read, (
        f"The Variable table in {rel(ENVIRONMENT_PAGE)} must list exactly the"
        f" environment variables src/git_hygiene reads. Add rows for"
        f" {sorted(read - documented)}; remove rows for {sorted(documented - read)}."
    )


def test_hooks_page_lists_every_hook_id():
    # type: () -> None
    manifest = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    ids = set(re.findall(r"^- id: (\S+)", manifest, re.MULTILINE))
    assert ids, "no hook ids found in .pre-commit-hooks.yaml"
    documented = spellings(HOOKS_PAGE, "Hook id")
    assert documented == ids, (
        f"The Hook id table in {rel(HOOKS_PAGE)} must list exactly the ids in"
        f" .pre-commit-hooks.yaml. Add rows for {sorted(ids - documented)};"
        f" remove rows for {sorted(documented - ids)}."
    )


def test_no_page_names_an_annex_path():
    # type: () -> None
    offenders = []
    for page in sorted(DOC_AI.rglob("*")):
        if page.is_file():
            text = page.read_text(encoding="utf-8", errors="replace")
            for match in ANNEX_PATH.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{rel(page)}:{line}")
    assert not offenders, (
        "doc/ai/ is published and must not name a path under the untracked a/"
        " directory. Remove the reference at: " + ", ".join(offenders)
    )
