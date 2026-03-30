"""
Prompt version changelog parser for tracking iteration history.

The prompt file (extract_actions.v1.txt) carries a structured changelog header
so every fix is traceable. Format:

    # CHANGELOG
    # v1.0 2026-03-29 — initial version
    # v1.1 2026-03-30 — add few-shot example 3 (FYI case)
    # v1.2 2026-03-31 — tighten confidence calibration bands
    # END_CHANGELOG

Usage:
    from digest_core.eval.changelog import parse_prompt_changelog
    versions = parse_prompt_changelog(Path("prompts/extract_actions.v1.txt"))
    for v in versions:
        print(v)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class PromptVersion:
    """A single entry in the prompt changelog."""

    version: str     # e.g. "v1.2"
    date: str        # YYYY-MM-DD
    note: str        # free-form description

    def __str__(self) -> str:
        return f"{self.version}  {self.date}  {self.note}"


# Pattern: # v1.2 2026-03-31 — some description
_ENTRY_RE = re.compile(
    r"^#\s+(v[\w.]+)\s+(\d{4}-\d{2}-\d{2})\s+[-–—]\s+(.+)$",
    re.MULTILINE,
)

_CHANGELOG_START = re.compile(r"^#\s*CHANGELOG\s*$", re.MULTILINE | re.IGNORECASE)
_CHANGELOG_END = re.compile(r"^#\s*END_CHANGELOG\s*$", re.MULTILINE | re.IGNORECASE)


def parse_prompt_changelog(prompt_path: Path) -> List[PromptVersion]:
    """
    Parse the CHANGELOG block from a prompt's companion ``.changelog`` file,
    falling back to an inline ``# CHANGELOG`` block within the prompt itself.

    The companion file (e.g. ``extract_actions.v1.changelog``) is preferred
    so that changelog metadata is never included in the text sent to the LLM.

    Returns an empty list if no changelog is found (backward compatible).
    """
    # Prefer companion .changelog file
    changelog_path = prompt_path.with_suffix(".changelog")
    if changelog_path.exists():
        text = changelog_path.read_text(encoding="utf-8")
    else:
        text = prompt_path.read_text(encoding="utf-8")

    return _parse_changelog_text(text)


def _parse_changelog_text(text: str) -> List[PromptVersion]:
    """Parse CHANGELOG entries from raw text."""
    start_m = _CHANGELOG_START.search(text)
    if not start_m:
        return []

    end_m = _CHANGELOG_END.search(text, start_m.end())
    block = text[start_m.end(): end_m.start()] if end_m else text[start_m.end():]

    return [
        PromptVersion(version=m.group(1), date=m.group(2), note=m.group(3).strip())
        for m in _ENTRY_RE.finditer(block)
    ]


def get_current_version(prompt_path: Path) -> Optional[str]:
    """Return the most recent version tag from the changelog, or None."""
    versions = parse_prompt_changelog(prompt_path)
    return versions[-1].version if versions else None


def format_changelog(versions: List[PromptVersion]) -> str:
    """Format the changelog for display."""
    if not versions:
        return "(no changelog entries found)"
    lines = ["Version  Date        Description", "-" * 60]
    for v in versions:
        lines.append(str(v))
    return "\n".join(lines)
