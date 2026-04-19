"""Roadmap markdown parser."""

from __future__ import annotations

from pathlib import Path

from ouroboros_api.services.roadmap_parser import discover_roadmap_files, parse_roadmap_file


SAMPLE = """# Future Roadmap

## Q1

### Ship v0.1 [x]

Initial release.

### SAML SSO

Status: planned

### Audit log export [in progress]

WIP.

## Q2

### Multi-region

Status: planned
"""


def test_parse_roadmap_extracts_entries(tmp_path: Path) -> None:
    f = tmp_path / "FUTURE_FEATURE_ROADMAP_2026.md"
    f.write_text(SAMPLE, encoding="utf-8")
    entries = parse_roadmap_file(f)
    titles = [e.title for e in entries]
    assert "Ship v0.1 [x]" in titles or "Ship v0.1" in titles
    assert any("SAML SSO" in t for t in titles)
    assert any("Multi-region" in t for t in titles)


def test_parse_roadmap_detects_status(tmp_path: Path) -> None:
    f = tmp_path / "ROADMAP.md"
    f.write_text(SAMPLE, encoding="utf-8")
    entries = parse_roadmap_file(f)
    by_title = {e.title: e for e in entries}
    done = next((e for t, e in by_title.items() if "Ship v0.1" in t), None)
    assert done is not None and done.status == "done"
    wip = next((e for t, e in by_title.items() if "Audit log export" in t), None)
    assert wip is not None and wip.status == "in_progress"


def test_parse_roadmap_classifies_kind(tmp_path: Path) -> None:
    f = tmp_path / "FUTURE_FEATURE_ROADMAP_2026.md"
    f.write_text(SAMPLE, encoding="utf-8")
    entries = parse_roadmap_file(f)
    assert entries and entries[0].kind == "future"


def test_discover_roadmap_files_finds_known_patterns(tmp_path: Path) -> None:
    (tmp_path / "FUTURE_FEATURE_ROADMAP_2026.md").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "PLANNED_FEATURE_ROADMAP.md").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "ROADMAP.md").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "unrelated.md").write_text("x", encoding="utf-8")
    found = sorted(p.name for p in discover_roadmap_files(tmp_path))
    assert "FUTURE_FEATURE_ROADMAP_2026.md" in found
    assert "PLANNED_FEATURE_ROADMAP.md" in found
    assert "ROADMAP.md" in found
    assert "unrelated.md" not in found
