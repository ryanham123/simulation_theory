#!/usr/bin/env python3
"""
Split monolithic book.txt (full LaTeX document or body starting at \\chapter) into
chapters/*.tex and backmatter/references.tex. Removes per-chapter thebibliography
blocks; merges unique \\bibitem entries into one references file.

Usage (from project root):
  python3 scripts/split_book.py

Requires book.txt on disk with \\chapter{...} markers (and ideally \\begin{document}
or body-only text).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book.txt"
CHAPTER_DIR = ROOT / "chapters"
BACKMATTER = ROOT / "backmatter" / "references.tex"


def slugify(title: str, max_len: int = 48) -> str:
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("ascii")
    title = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return title[:max_len].rstrip("-")


def strip_outer_wrapper(text: str) -> str:
    if "\\begin{document}" in text:
        text = re.sub(
            r"^.*\\begin\{document\}\s*",
            "",
            text,
            count=1,
            flags=re.DOTALL,
        )
        text = re.sub(r"\\tableofcontents\s*", "", text, count=1)
    text = re.sub(r"\\end\{document\}\s*$", "", text, flags=re.DOTALL)
    return text.strip()


def extract_bibitems(text: str) -> dict[str, str]:
    items: dict[str, str] = {}
    pattern = re.compile(
        r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        key, body = m.group(1).strip(), m.group(2).strip()
        if key not in items:
            items[key] = body
    return items


def strip_trailing_bibliography(chunk: str) -> str:
    chunk = re.sub(
        r"\s*\\vspace\{[^}]+\}\s*"
        r"(?:\\noindent\\textbf\{References\}.*?)??"
        r"\\begin\{thebibliography\}\{[^}]+\}.*?\\end\{thebibliography\}\s*$",
        "",
        chunk,
        flags=re.DOTALL,
    )
    return chunk.rstrip()


def main() -> None:
    raw = BOOK.read_text(encoding="utf-8")
    if raw.lstrip().startswith("%") and "\\chapter{" not in raw:
        raise SystemExit(
            f"{BOOK.name} looks like a pointer stub. Paste or save your full manuscript, "
            "then rerun this script."
        )
    if len(raw.strip()) < 500:
        raise SystemExit(
            f"{BOOK} is missing or nearly empty. Save your manuscript, then rerun."
        )

    all_bib = extract_bibitems(raw)
    body = strip_outer_wrapper(raw)
    parts = re.split(r"(?=\\chapter\{)", body)
    chapters = [p for p in parts if p.strip().startswith("\\chapter{")]

    if not chapters:
        raise SystemExit("No \\chapter{...} blocks found.")

    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    include_lines: list[str] = []

    for idx, chunk in enumerate(chapters, start=1):
        m = re.match(r"\\chapter\{(.*)\}", chunk.strip(), re.DOTALL)
        if not m:
            raise SystemExit(f"Bad chapter header near: {chunk[:80]!r}")
        title = m.group(1).strip().replace("\n", " ")
        slug = slugify(title)
        nn = f"{idx:02d}-{slug}"
        cleaned = strip_trailing_bibliography(chunk)
        out = CHAPTER_DIR / f"{nn}.tex"
        out.write_text(cleaned + "\n", encoding="utf-8")
        include_lines.append(f"\\include{{chapters/{nn}}}")
        print(f"Wrote {out.relative_to(ROOT)}")

    includes_path = CHAPTER_DIR / "_includes.tex"
    includes_path.write_text("\n".join(include_lines) + "\n", encoding="utf-8")
    print(f"Wrote {includes_path.relative_to(ROOT)}")

    lines = [
        "\\chapter*{References}",
        "\\addcontentsline{toc}{chapter}{References}",
        "\\begin{thebibliography}{99}",
    ]
    for key in sorted(all_bib.keys()):
        lines.append(f"\\bibitem{{{key}}}")
        lines.append(all_bib[key])
        if not all_bib[key].endswith("\n"):
            lines.append("")
    lines.append("\\end{thebibliography}")
    lines.append("")
    BACKMATTER.parent.mkdir(parents=True, exist_ok=True)
    BACKMATTER.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {BACKMATTER.relative_to(ROOT)} ({len(all_bib)} entries)")


if __name__ == "__main__":
    main()
