"""Hold the decision index and the decision records one-to-one.

A record missing from the index cannot be found, and an index row whose
file is gone is a link to nothing. Neither announces itself, so this does.
"""

import re
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "doc"
DECISIONS = DOC / "design" / "decisions"
PROPOSALS = DOC / "proposal"

RECORD_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
INDEX_ROW = re.compile(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|")
PROPOSAL_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def _records():
    names = sorted(p.name for p in DECISIONS.iterdir() if p.name != "index.md")
    for name in names:
        assert RECORD_NAME.match(name), "badly named decision record: " + name
    return names


def _index_rows():
    text = (DECISIONS / "index.md").read_text(encoding="utf-8")
    return [m.groups() for m in map(INDEX_ROW.match, text.splitlines()) if m]


def test_index_lists_every_record_exactly_once():
    rows = _index_rows()
    linked = [target for _number, target in rows]
    assert sorted(linked) == _records()
    assert len(linked) == len(set(linked))
    for number, target in rows:
        assert target.startswith(number + "-"), f"row {number} links {target}"


def test_records_are_numbered_without_gaps():
    numbers = [int(name[:4]) for name in _records()]
    assert numbers == list(range(1, len(numbers) + 1))


def test_each_record_carries_its_number_date_and_status():
    for name in _records():
        lines = (DECISIONS / name).read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("# " + name[:4] + ". "), name
        head = lines[1:6]
        assert any(re.match(r"^Date: \d{4}-\d{2}-\d{2}$", line) for line in head), name
        assert any(line.startswith("Status: ") for line in head), name


def test_proposals_are_dated_and_carry_a_status():
    for path in sorted(PROPOSALS.iterdir()):
        assert PROPOSAL_NAME.match(path.name), "badly named proposal: " + path.name
        text = path.read_text(encoding="utf-8")
        assert re.search(r"^(\| Status \||Status:)", text, re.MULTILINE), path.name
