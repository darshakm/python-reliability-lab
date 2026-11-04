from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def test_local_markdown_links_resolve() -> None:
    failures: list[str] = []
    markdown_files = [PROJECT_ROOT / "README.md", *PROJECT_ROOT.glob("docs/**/*.md")]

    for document in markdown_files:
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.split("#", maxsplit=1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                failures.append(
                    f"{document.relative_to(PROJECT_ROOT)} -> {raw_target}"
                )

    assert not failures, "broken local Markdown links:\n" + "\n".join(failures)


def test_study_companion_has_all_concept_chapters() -> None:
    chapters = sorted((PROJECT_ROOT / "docs" / "concepts").glob("*.md"))

    assert len(chapters) == 10
    assert chapters[0].name.startswith("01-")
    assert chapters[-1].name.startswith("10-")
