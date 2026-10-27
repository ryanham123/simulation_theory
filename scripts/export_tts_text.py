#!/usr/bin/env python3
"""
Export the book as plain UTF-8 text for text-to-speech (TTS) tools.

Reads the same \\input/\\include sequence as main.tex (skips the title page
macros; uses \\title/\\author from main.tex instead), strips LaTeX markup, and
writes a single .txt file.

Usage (from project root):
  python3 scripts/export_tts_text.py
  python3 scripts/export_tts_text.py -o my_book.txt --skip-references
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TTS_ACRONYM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("SSA", "S. S. A."),
    ("AI", "A. I."),
)


def parse_brace_group(s: str, i: int) -> tuple[str, int]:
    """s[i] must be '{'. Returns (inner_text, index_after_closing_brace)."""
    if i >= len(s) or s[i] != "{":
        raise ValueError("expected '{'")
    depth = 1
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        elif c == "\\" and j + 1 < len(s):
            j += 1
        j += 1
    raise ValueError("unbalanced {}")


def extract_brace_command(source: str, cmd: str) -> str | None:
    pat = re.compile(rf"\\{re.escape(cmd)}\s*\{{")
    m = pat.search(source)
    if not m:
        return None
    inner, _ = parse_brace_group(source, m.end() - 1)
    return inner


def strip_percent_comments(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if not line.endswith("\n"):
            line = line + "\n"
        i = 0
        buf: list[str] = []
        while i < len(line):
            c = line[i]
            if c == "%" and (i == 0 or line[i - 1] != "\\"):
                break
            buf.append(c)
            i += 1
        out.append("".join(buf).rstrip() + "\n")
    return "".join(out)


def find_matching_end(text: str, start: int, env: str) -> int:
    """Index of '\\end{env}' that closes the '\\begin{env}' at ``start``."""
    begin_re = re.compile(rf"\\begin\{{{re.escape(env)}\}}")
    end_re = re.compile(rf"\\end\{{{re.escape(env)}\}}")
    m0 = begin_re.match(text, start)
    if not m0:
        raise ValueError(f"expected \\\\begin{{{env}}} at {start}")
    depth = 1
    pos = m0.end()
    while depth:
        mb = begin_re.search(text, pos)
        me = end_re.search(text, pos)
        if me is None:
            raise ValueError(f"missing \\end{{{env}}}")
        if mb is not None and mb.start() < me.start():
            depth += 1
            pos = mb.end()
        else:
            depth -= 1
            if depth == 0:
                return me.start()
            pos = me.end()
    raise ValueError(f"missing \\end{{{env}}}")


def process_itemize_inner(inner: str) -> str:
    items = re.split(r"\\item\s*", inner)
    parts: list[str] = []
    for raw in items:
        chunk = raw.strip()
        if not chunk:
            continue
        parts.append("• " + chunk)
    return "\n".join(parts)


def process_enumerate_inner(inner: str) -> str:
    items = re.split(r"\\item\s*", inner)
    parts: list[str] = []
    n = 0
    for raw in items:
        chunk = raw.strip()
        if not chunk:
            continue
        n += 1
        parts.append(f"{n}. {chunk}")
    return "\n".join(parts)


def process_plain_environment(inner: str) -> str:
    return inner.strip()


def process_description_inner(inner: str) -> str:
    """Glossary-style \\item[term] entries -> 'Term. Definition' for TTS."""
    parts: list[str] = []
    for raw in re.split(r"\\item\s*\[", inner):
        chunk = raw.strip()
        if not chunk:
            continue
        bracket_end = chunk.find("]")
        if bracket_end < 0:
            continue
        term = chunk[:bracket_end].strip()
        definition = chunk[bracket_end + 1 :].strip()
        if not term or not definition:
            continue
        parts.append(f"{term}. {definition}")
    return "\n\n".join(parts)


def process_labeled_box(label: str):
    def inner_fn(inner: str) -> str:
        body = inner.strip()
        if not body:
            return ""
        return f"{label}. {body}"

    return inner_fn


def process_tabularx_inner(inner: str) -> str:
    text = inner
    text = re.sub(r"\\(toprule|midrule|bottomrule)\b", "", text)
    text = re.sub(r"\\textwidth\b", "", text)
    text = re.sub(r">\{[^{}]*\}", "", text)
    text = re.sub(r"p\{[^{}]*\}", "", text)
    text = re.sub(r"\{[A-Z]+\}", "", text)
    rows = [row.strip() for row in re.split(r"\\\\", text) if row.strip()]
    out: list[str] = []
    for i, row in enumerate(rows):
        cols = [latex_to_plain(col).strip() for col in row.split("&")]
        cols = [col for col in cols if col]
        if not cols:
            continue
        if i == 0:
            out.append("Table.")
            out.append(" Columns: " + "; ".join(cols) + ".")
            continue
        if len(cols) == 1:
            out.append(cols[0])
            continue
        head, rest = cols[0], cols[1:]
        out.append(f"{head}: " + "; ".join(rest) + ".")
    return "\n".join(out)


def replace_environment_block(text: str, env: str, inner_fn) -> str:
    begin = rf"\begin{{{env}}}"
    end = rf"\end{{{env}}}"
    while begin in text:
        i = text.find(begin)
        k = find_matching_end(text, i, env)
        k_end = text.find(end, k)
        if k_end < 0:
            break
        j = i + len(begin)
        while j < k and text[j].isspace():
            j += 1
        if j < k and text[j] == "{":
            _, j = parse_brace_group(text, j)
        if j < k and text[j] == "[":
            depth = 1
            jj = j + 1
            while jj < k and depth:
                if text[jj] == "[":
                    depth += 1
                elif text[jj] == "]":
                    depth -= 1
                jj += 1
            j = jj
        while j < k and text[j].isspace():
            j += 1
        inner = text[j:k].strip()
        replacement = inner_fn(inner)
        text = text[:i] + "\n" + replacement + "\n" + text[k_end + len(end) :]
    return text


def unwrap_commands(text: str) -> str:
    """Repeatedly unwrap simple one-argument formatting commands."""
    one_arg = (
        "textbf",
        "textit",
        "emph",
        "textsl",
        "textsc",
        "texttt",
        "underline",
        "Huge",
        "huge",
        "LARGE",
        "Large",
        "large",
        "normalsize",
        "small",
        "footnotesize",
        "scriptsize",
        "tiny",
    )
    changed = True
    while changed:
        changed = False
        for cmd in one_arg:
            pat = re.compile(rf"\\{cmd}\s*\{{")
            m = pat.search(text)
            if not m:
                continue
            inner, end_i = parse_brace_group(text, m.end() - 1)
            text = text[: m.start()] + inner + text[end_i:]
            changed = True
            break
    return text


def strip_zero_arg_commands(text: str) -> str:
    for cmd in (
        "noindent",
        "centering",
        "par",
        "makeatletter",
        "makeatother",
        "newline",
        "linebreak",
    ):
        text = re.sub(rf"\\{cmd}\b\s*", "", text)
    text = re.sub(r"\\vspace\*?\{[^}]*\}", "\n", text)
    text = re.sub(r"\\hspace\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\vfill\b\s*", "\n", text)
    return text


def _heading_plain(kind: str, starred: bool, title: str) -> str:
    title = unwrap_commands(title).strip()
    if starred:
        return f"\n\n{title}\n\n"
    return f"\n\n{title}\n\n"


def strip_structural_commands(text: str) -> str:
    pat = re.compile(r"\\(chapter|section|subsection)(\*)?(?:\[[^\]]*\])?\s*\{")
    chapter_n = 0
    while True:
        m = pat.search(text)
        if not m:
            break
        kind = m.group(1)
        starred = m.group(2) is not None
        title, end_i = parse_brace_group(text, m.end() - 1)
        if kind == "chapter" and not starred:
            chapter_n += 1
            plain_title = unwrap_commands(title).strip()
            replacement = f"\n\nChapter {chapter_n}. {plain_title}\n\n"
        else:
            replacement = _heading_plain(kind, starred, title)
        text = text[: m.start()] + replacement + text[end_i:]
    text = re.sub(r"\\addcontentsline\{[^}]*\}\{[^}]*\}\{[^}]*\}\s*", "", text)
    text = re.sub(r"\\tableofcontents\s*", "", text)
    text = re.sub(r"\\(frontmatter|mainmatter|backmatter)\b\s*", "\n", text)
    return text


def strip_citations_and_refs(text: str) -> str:
    text = re.sub(
        r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{[^}]*\}",
        "",
        text,
    )
    text = re.sub(r"\\(ref|eqref|pageref|autoref|label)\{[^}]*\}", "", text)
    return text


def footnotes_to_text(text: str) -> str:
    while True:
        m = re.search(r"\\footnote\s*\{", text)
        if not m:
            break
        start = m.start()
        inner, end_i = parse_brace_group(text, m.end() - 1)
        plain = latex_to_plain(inner).strip()
        text = text[:start] + f" (Footnote: {plain})" + text[end_i:]
    return text


def url_to_text(text: str) -> str:
    while True:
        m = re.search(r"\\url\s*\{", text)
        if not m:
            break
        inner, end_i = parse_brace_group(text, m.end() - 1)
        text = text[: m.start()] + inner.strip() + text[end_i:]
    return text


def bibitem_body(text: str) -> str:
    """Turn bibliography chunk into readable lines (strip \\bibitem lines)."""
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("\\bibitem"):
            continue
        if line:
            lines.append(line)
    return "\n".join(lines)


def latex_to_plain(tex: str) -> str:
    tex = strip_percent_comments(tex)
    tex = strip_zero_arg_commands(tex)
    tex = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", tex, flags=re.DOTALL)

    # Environments (outermost repeated)
    for env, fn in (
        ("itemize", process_itemize_inner),
        ("enumerate", process_enumerate_inner),
        ("center", process_plain_environment),
        ("quote", process_plain_environment),
        ("description", process_description_inner),
        # Innermost first: compactchecklist wraps \item bodies (see preamble \newenvironment).
        ("compactchecklist", process_itemize_inner),
        ("mythvsfactbox", process_labeled_box("Myth vs. Fact")),
        ("commonquestionbox", process_labeled_box("Common question")),
        ("quickpracticebox", process_labeled_box("Quick practice")),
        ("tonightbox", process_labeled_box("What to do tonight")),
        ("examplebox", process_labeled_box("Example")),
        ("keytakeawaybox", process_labeled_box("Key takeaway")),
        ("safetynotebox", process_labeled_box("Safety note")),
        ("whyitmattersbox", process_labeled_box("Why it matters")),
        ("readerstorybox", process_labeled_box("Reader story")),
        ("beginnermistakebox", process_labeled_box("Beginner mistake")),
        ("researchnotebox", process_labeled_box("Research note")),
        ("chaptermapbox", process_labeled_box("Chapter map")),
        ("tabularx", process_tabularx_inner),
    ):
        tex = replace_environment_block(tex, env, fn)

    # Bibliography: keep text, drop keys
    while r"\begin{thebibliography}" in tex:
        i = tex.find(r"\begin{thebibliography}")
        j = find_matching_end(tex, i, "thebibliography")
        end_marker = r"\end{thebibliography}"
        k = tex.find(end_marker, j)
        if k < 0:
            break
        after = i + len(r"\begin{thebibliography}")
        while after < len(tex) and tex[after].isspace():
            after += 1
        if after < len(tex) and tex[after] == "{":
            _, after = parse_brace_group(tex, after)
        while after < len(tex) and tex[after].isspace():
            after += 1
        inner = tex[after:j]
        body = bibitem_body(inner)
        tex = tex[:i] + "\n\nReferences.\n\n" + body + "\n\n" + tex[k + len(end_marker) :]

    tex = strip_structural_commands(tex)
    tex = strip_citations_and_refs(tex)
    tex = url_to_text(tex)
    tex = footnotes_to_text(tex)

    # \textsuperscript{n}
    while True:
        m = re.search(r"\\textsuperscript\s*\{", tex)
        if not m:
            break
        inner, end_i = parse_brace_group(tex, m.end() - 1)
        tex = tex[: m.start()] + inner + tex[end_i:]

    tex = re.sub(r"\\ldots\b", "...", tex)
    tex = re.sub(r"\\dots\b", "...", tex)
    tex = tex.replace("``", "\u201c").replace("''", "\u201d")
    tex = tex.replace("`", "'")
    tex = re.sub(r"\\%", "%", tex)
    tex = re.sub(r"\\#", "#", tex)
    tex = re.sub(r"\\_", "_", tex)
    tex = tex.replace(r"\&", "and")
    tex = re.sub(r"~", " ", tex)
    tex = re.sub(r"(\d)--(\d)", r"\1 to \2", tex)
    tex = tex.replace("---", " — ")
    tex = tex.replace("--", "–")

    tex = unwrap_commands(tex)
    tex = strip_zero_arg_commands(tex)

    # Drop stray documentclass, input preamble, etc.
    tex = re.sub(r"\\documentclass(\[[^\]]*\])?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\input\{[^}]+\}", "", tex)
    tex = re.sub(r"\\include\{[^}]+\}", "", tex)
    tex = re.sub(r"\\usepackage(\[[^\]]*\])?\{[^}]*\}", "", tex)

    # Remaining unknown commands: remove command name, keep braced arg if present
    def strip_unknown(m: re.Match[str]) -> str:
        full = m.group(0)
        if full.endswith("{") and m.end() < len(m.string):
            try:
                inner, _ = parse_brace_group(m.string, m.end() - 1)
                return inner
            except ValueError:
                return ""
        return ""

    for _ in range(50):
        new = re.sub(
            r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?\{",
            strip_unknown,
            tex,
        )
        if new == tex:
            break
        tex = new
    tex = re.sub(r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?", "", tex)
    tex = re.sub(r"\\\\\s*", "\n", tex)
    tex = tex.replace(r"\$", "$")
    tex = tex.replace(r"\%", "%")
    tex = tex.replace(r"\#", "#")
    tex = tex.replace(r"\_", "_")
    tex = tex.replace(r"\&", "and")
    tex = tex.replace(r"\ ", " ")
    tex = tex.replace(r"\.", ".")
    tex = tex.replace(r"\,", ",")
    tex = tex.replace(r"\:", ":")
    tex = tex.replace(r"\;", ";")

    tex = re.sub(r"\{([^{}]*)\}", r"\1", tex)
    tex = re.sub(r"[ \t]+\n", "\n", tex)
    tex = re.sub(r"\n{3,}", "\n\n", tex)
    tex = re.sub(r" +", " ", tex)
    tex = re.sub(r" \.", ".", tex)
    tex = re.sub(r" ,", ",", tex)
    tex = re.sub(r" :", ":", tex)
    tex = re.sub(r" ;", ";", tex)
    return tex.strip()


def normalize_for_tts(text: str) -> str:
    text = re.sub(r"\be\.g\.,?", "for example", text)
    text = re.sub(r"\bi\.e\.,?", "that is", text)
    text = re.sub(r"\bet al\.", "and colleagues", text)
    text = re.sub(r"\betc\.", "and so on", text)
    text = re.sub(r"\bvs\.\b", "versus", text)
    text = re.sub(r"\bca\.\s*", "around ", text)
    text = re.sub(r"\be\.g\.\s*", "for example ", text)
    text = re.sub(r"\bi\.e\.\s*", "that is ", text)
    text = text.replace("No.", "Number")
    text = re.sub(r"\bpp\.\s*", "pages ", text)
    text = re.sub(r"\bVol\.\s*", "Volume ", text)
    text = re.sub(r"\bFig\.\s*", "Figure ", text)
    text = re.sub(r"\bChs?\.\s*", "Chapters ", text)
    text = text.replace("Reader safety note:", "Reader safety note.")
    for source, spoken in _TTS_ACRONYM_REPLACEMENTS:
        text = re.sub(rf"\b{re.escape(source)}\b", spoken, text)
    text = re.sub(r"\bChapter\. ", "Chapter ", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_includes(main_tex: str) -> list[str]:
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", main_tex, re.DOTALL)
    if not m:
        raise ValueError("main.tex: no \\begin{document} ... \\end{document}")
    body = m.group(1)
    paths: list[str] = []
    for mm in re.finditer(r"\\(?:input|include)\{([^}]+)\}", body):
        p = mm.group(1).strip()
        if not p.endswith(".tex"):
            p += ".tex"
        paths.append(p)
    return paths


def read_tex_file(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def build_manuscript(root: Path, *, skip_references: bool) -> str:
    main = read_tex_file(root, "main.tex")
    title = extract_brace_command(main, "title") or "Untitled"
    author = extract_brace_command(main, "author") or ""

    header = f"{unwrap_commands(title).strip()}\n"
    if author:
        header += f"By {unwrap_commands(author).strip()}\n"
    header += "\n"

    pieces: list[str] = [header]
    for rel in parse_includes(main):
        if rel.replace("\\", "/").endswith("frontmatter/titlepage.tex"):
            continue
        if skip_references and rel.replace("\\", "/").endswith("backmatter/references.tex"):
            continue
        pieces.append(read_tex_file(root, rel))

    return "\n\n".join(pieces)


def export_tts_text(
    root: Path | None = None,
    *,
    output: Path | None = None,
    skip_references: bool = True,
) -> Path:
    root = (root or ROOT).resolve()
    out = output or (root / "book_tts.txt")
    raw = build_manuscript(root, skip_references=skip_references)
    plain = normalize_for_tts(latex_to_plain(raw))
    out.write_text(plain + "\n", encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Export book LaTeX to audiobook-friendly plain text for TTS.")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .txt path (default: book_tts.txt in project root)",
    )
    refs = ap.add_mutually_exclusive_group()
    refs.add_argument(
        "--skip-references",
        action="store_true",
        default=True,
        help="Omit backmatter/references.tex from the export (default).",
    )
    refs.add_argument(
        "--include-references",
        action="store_true",
        help="Include backmatter/references.tex in the export.",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root (directory containing main.tex)",
    )
    args = ap.parse_args()
    path = export_tts_text(
        args.root,
        output=args.output,
        skip_references=not args.include_references,
    )
    print(path)


if __name__ == "__main__":
    main()
