#!/usr/bin/env python3
"""
Check LaTeX citation keys in this book against backmatter/references.tex.

Reports:
  - undefined keys (\\cite{...} with no matching \\bibitem{...})
  - orphan keys (\\bibitem{...} never cited in the manuscript)
  - duplicate \\bibitem keys

Usage (from project root):
  python3 scripts/check_citations.py
  python3 scripts/check_citations.py --verbose
  python3 scripts/check_citations.py --references backmatter/references.tex
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCES = ROOT / "backmatter" / "references.tex"
CITE_RE = re.compile(r"\\cite(?:\[[^\]]*\])?\{([^}]+)\}")
BIBITEM_RE = re.compile(r"\\bibitem\{([^}]+)\}")


@dataclass
class CitationCheckResult:
    ok: bool
    tex_files_scanned: int
    references_path: Path
    cited_keys: set[str] = field(default_factory=set)
    bibitem_keys: set[str] = field(default_factory=set)
    undefined: list[str] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    duplicate_bibitems: list[str] = field(default_factory=list)
    cite_locations: dict[str, list[str]] = field(default_factory=dict)
    bibitem_lines: dict[str, int] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate \\cite keys against \\bibitem entries in references.tex.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root to search for .tex files (default: repo root).",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=DEFAULT_REFERENCES,
        help="Path to references.tex containing \\bibitem entries.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every cited key and its source locations.",
    )
    parser.add_argument(
        "--warn-orphans",
        action="store_true",
        default=True,
        help="Warn about uncited \\bibitem keys (default: on).",
    )
    parser.add_argument(
        "--no-warn-orphans",
        action="store_false",
        dest="warn_orphans",
        help="Do not warn about uncited \\bibitem keys.",
    )
    return parser.parse_args()


def split_cite_keys(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def collect_cites(tex_files: list[Path], *, root: Path) -> dict[str, list[str]]:
    cites: dict[str, list[str]] = defaultdict(list)

    for path in tex_files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in CITE_RE.finditer(line):
                for key in split_cite_keys(match.group(1)):
                    cites[key].append(f"{rel}:{line_no}")

    return cites


def collect_bibitems(references_path: Path) -> tuple[dict[str, int], list[str]]:
    text = references_path.read_text(encoding="utf-8", errors="replace")
    bibitems: dict[str, int] = {}
    duplicates: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in BIBITEM_RE.finditer(line):
            key = match.group(1).strip()
            if key in bibitems:
                duplicates.append(key)
            bibitems[key] = line_no
    return bibitems, duplicates


def discover_tex_files(root: Path, references_path: Path) -> list[Path]:
    files = sorted(root.rglob("*.tex"))
    return [path for path in files if path.resolve() != references_path.resolve()]


def check_citations(
    *,
    root: Path | None = None,
    references: Path | None = None,
) -> CitationCheckResult:
    root = (root or ROOT).resolve()
    references_path = (references or DEFAULT_REFERENCES).resolve()

    if not references_path.is_file():
        raise FileNotFoundError(f"References file not found: {references_path}")

    tex_files = discover_tex_files(root, references_path)
    cites = collect_cites(tex_files, root=root)
    bibitems, duplicate_bibitems = collect_bibitems(references_path)

    cited_keys = set(cites)
    bib_keys = set(bibitems)
    undefined = sorted(cited_keys - bib_keys)
    orphans = sorted(bib_keys - cited_keys)
    duplicates = sorted(set(duplicate_bibitems))

    return CitationCheckResult(
        ok=not undefined and not duplicates,
        tex_files_scanned=len(tex_files),
        references_path=references_path,
        cited_keys=cited_keys,
        bibitem_keys=bib_keys,
        undefined=undefined,
        orphans=orphans,
        duplicate_bibitems=duplicates,
        cite_locations=dict(cites),
        bibitem_lines=bibitems,
    )


def format_citation_report(result: CitationCheckResult, *, root: Path, verbose: bool = False) -> str:
    try:
        references_rel = result.references_path.relative_to(root)
    except ValueError:
        references_rel = result.references_path

    lines = [
        f"Scanned {result.tex_files_scanned} .tex files",
        f"References: {references_rel}",
        f"Cited keys: {len(result.cited_keys)}",
        f"Bibitem keys: {len(result.bibitem_keys)}",
        "",
    ]

    if result.duplicate_bibitems:
        lines.append("Duplicate \\bibitem keys:")
        for key in result.duplicate_bibitems:
            lines.append(f"  {key}")
        lines.append("")

    if result.undefined:
        lines.append("Undefined citations (\\cite key missing from references.tex):")
        for key in result.undefined:
            lines.append(f"  {key}")
            for location in result.cite_locations.get(key, []):
                lines.append(f"    {location}")
        lines.append("")

    if result.orphans:
        lines.append("Orphan bibliography entries (\\bibitem never cited):")
        for key in result.orphans:
            line_no = result.bibitem_lines[key]
            lines.append(f"  {key}  (references.tex:{line_no})")
        lines.append("")

    if verbose and result.cite_locations:
        lines.append("Citation map:")
        for key in sorted(result.cite_locations):
            lines.append(f"  {key}")
            for location in result.cite_locations[key]:
                lines.append(f"    {location}")
        lines.append("")

    if result.ok:
        if result.orphans:
            lines.append("Structural check passed (no undefined or duplicate keys).")
            lines.append(f"Note: {len(result.orphans)} uncited bibliography entries remain.")
        else:
            lines.append("Citation check passed.")
    else:
        lines.append("Citation check failed.")

    return "\n".join(lines)


def print_citation_report(
    result: CitationCheckResult,
    *,
    root: Path,
    verbose: bool = False,
    warn_orphans: bool = True,
) -> int:
    report = format_citation_report(result, root=root, verbose=verbose)
    print(report)
    if not result.ok:
        print("Citation check failed.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    references_path = args.references.resolve()

    try:
        result = check_citations(root=root, references=references_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not result.tex_files_scanned:
        print(f"No .tex files found under {root}", file=sys.stderr)
        return 1

    if not args.warn_orphans:
        result.orphans = []

    return print_citation_report(
        result,
        root=root,
        verbose=args.verbose,
        warn_orphans=args.warn_orphans,
    )


if __name__ == "__main__":
    raise SystemExit(main())
