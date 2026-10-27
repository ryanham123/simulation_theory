#!/usr/bin/env python3
"""
Use Codex to review and revise the LaTeX book rooted at ``main.tex`` using the
instructions stored in ``setup_prompt.txt``.

This script builds a revision chain with these core steps:
1. Score the manuscript before revisions.
2. Audit citations using the check-resource-citations skill.
3. Audit human voice using the humanize-book-voice skill.
4. Optionally audit Kindle Direct Publishing (KDP) ebook readiness.
5. Read the manuscript and propose concrete edits (including citation and voice fixes).
6. Implement those edits directly in the manuscript files.
7. Score the manuscript after revisions.

Before the chain starts, ``scripts/check_citations.py`` and ``scripts/check_ai_voice.py``
run as structural pre-flights. After a successful run, both checkers run again.

Usage:
  python3 scripts/revise_book_with_codex.py
  python3 scripts/revise_book_with_codex.py --dry-run
  python3 scripts/revise_book_with_codex.py --setup-prompt my_prompt.txt
  python3 scripts/revise_book_with_codex.py --skip-citations
  python3 scripts/revise_book_with_codex.py --skip-human-voice
  python3 scripts/revise_book_with_codex.py --kdp-ebook
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# gpt-5.4 is rejected for ChatGPT-account Codex logins. This slug is in the
# current account catalog and can be overridden with --model.
DEFAULT_MODEL = "gpt-6-astra"
SCRIPTS_DIR = Path(__file__).resolve().parent
CHAIN_RUNNER = SCRIPTS_DIR / "run_codex_prompt_chain.py"
CITATION_SKILL = ROOT / ".cursor" / "skills" / "check-resource-citations" / "SKILL.md"
VOICE_SKILL = ROOT / ".cursor" / "skills" / "humanize-book-voice" / "SKILL.md"
DEFAULT_REFERENCES = ROOT / "backmatter" / "references.tex"
INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
STEP_DIR_RE = re.compile(r"^(\d+)-(.+)$")

SCORING_RUBRIC = """Here are the 10 characteristics that make a great non-fiction book, listed in text format with their weightings:
1. Clarity & Accessibility - 15%
2. Actionable Value - 14%
3. Credibility & Accuracy - 13%
4. Engaging Storytelling - 12%
5. Strong Structure & Flow - 11%
6. Authentic Voice & Tone - 10%
7. Clear Purpose & Promise - 9%
8. Reader Empathy - 7%
9. Visual & Structural Aids - 5%
10. Inspiring & Uplifting Tone - 4%
Total: 100%"""

KDP_EBOOK_GUIDANCE = """Prepare the manuscript for sale as a Kindle ebook on Amazon KDP.

Optimize for reflowable ebook reading rather than print layout. In particular:
- Remove or rewrite print-only language such as references to page numbers, facing pages, margins, or layout positions.
- Prefer short, scannable paragraphs and headings that work well on small screens.
- Flag tables, side-by-side comparisons, or other wide layouts that may break badly on Kindle devices; convert them to linear prose or lists when appropriate.
- Preserve navigability: chapter titles, appendix labels, glossary, and references should remain clear and easy to traverse in an ebook table of contents.
- Avoid instructions that depend on color, large pages, or fixed visual placement.
- Keep front matter and back matter ebook-friendly, including concise copyright/intro material and a clean references section.
- Favor reader experience on phones, tablets, and Kindle e-readers over print-style ornamentation.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review and revise the book starting at main.tex using instructions "
            "from setup_prompt.txt."
        )
    )
    parser.add_argument(
        "--setup-prompt",
        type=Path,
        default=ROOT / "setup_prompt.txt",
        help="Text file containing editorial instructions for Codex.",
    )
    parser.add_argument(
        "--book-entry",
        type=Path,
        default=ROOT / "main.tex",
        help="Entry-point .tex file for the manuscript.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT,
        help="Repository root / Codex working directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for the generated chain file and Codex artifacts.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=(
            "Codex model passed through to the chain runner. "
            f"Defaults to {DEFAULT_MODEL}."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the chain and render prompts without contacting Codex.",
    )
    parser.add_argument(
        "--skip-citations",
        action="store_true",
        help="Skip citation pre-flight, audit step, and post-run citation check.",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=DEFAULT_REFERENCES,
        help="Bibliography file for citation checks (default: backmatter/references.tex).",
    )
    parser.add_argument(
        "--skip-human-voice",
        action="store_true",
        help="Skip human-voice pre-flight, audit step, and post-run voice check.",
    )
    parser.add_argument(
        "--kdp-ebook",
        action="store_true",
        help="Add a Kindle Direct Publishing ebook-readiness audit and revision goals.",
    )
    return parser.parse_args()


def load_skill_text(path: Path, *, label: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} skill not found: {path}") from exc

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


def load_citation_checker():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import check_citations

    return check_citations


def load_voice_checker():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import check_ai_voice

    return check_ai_voice


def load_citation_skill_text(path: Path = CITATION_SKILL) -> str:
    return load_skill_text(path, label="Citation")


def load_voice_skill_text(path: Path = VOICE_SKILL) -> str:
    return load_skill_text(path, label="Human voice")


def run_structural_citation_check(
    *,
    workspace: Path,
    references: Path,
) -> tuple[Any, str]:
    checker = load_citation_checker()
    result = checker.check_citations(root=workspace, references=references)
    report = checker.format_citation_report(result, root=workspace)
    return result, report


def run_structural_voice_check(*, workspace: Path) -> tuple[Any, str]:
    checker = load_voice_checker()
    result = checker.check_ai_voice(root=workspace)
    report = checker.format_voice_report(result)
    return result, report


def load_prompt_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Setup prompt not found: {path}") from exc

    if not text.strip():
        raise SystemExit(
            f"Setup prompt is empty: {path}\n"
            "Add the editorial instructions you want Codex to follow, then rerun."
        )
    return text.strip()


def normalize_tex_target(raw: str, *, base_dir: Path) -> Path:
    candidate = Path(raw)
    if candidate.suffix:
        return (base_dir / candidate).resolve()
    return (base_dir / f"{raw}.tex").resolve()


def discover_tex_files(entry: Path) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen or not path.is_file():
            return

        seen.add(path)
        ordered.append(path)

        text = path.read_text(encoding="utf-8")
        for match in INCLUDE_RE.finditer(text):
            child = normalize_tex_target(match.group(1), base_dir=path.parent)
            visit(child)

    visit(entry.resolve())
    return ordered


def relative_list(paths: list[Path], *, workspace: Path) -> list[str]:
    items: list[str] = []
    for path in paths:
        try:
            items.append(str(path.relative_to(workspace)))
        except ValueError:
            items.append(str(path))
    return items


def build_review_prompt(
    *,
    setup_prompt: str,
    book_entry: Path,
    files_in_scope: list[str],
    include_citation_audit: bool,
    include_voice_audit: bool,
    include_kdp_ebook_audit: bool,
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    audit_blocks = """
Use the before-revision quality score to prioritize work. Target the lowest-scoring rubric categories first.

Before-revision score:
{{output:score_book_before}}
"""
    audit_constraints = (
        "- Prioritize edits that address the weakest rubric categories from the before-revision score.\n"
    )
    if include_citation_audit:
        audit_blocks += """
Incorporate the citation audit into your revision plan.

Citation audit:
{{output:audit_citations}}
"""
        audit_constraints += (
            "- Include citation fixes flagged by the audit when they affect credibility or accuracy.\n"
        )
    if include_voice_audit:
        audit_blocks += """
Incorporate the human-voice audit into your revision plan.

Human-voice audit:
{{output:audit_human_voice}}
"""
        audit_constraints += (
            "- Include voice fixes that make prose sound more human while staying professional.\n"
        )
    if include_kdp_ebook_audit:
        audit_blocks += """
Incorporate the KDP ebook-readiness audit into your revision plan.

KDP ebook-readiness audit:
{{output:audit_kdp_ebook}}
"""
        audit_constraints += (
            "- Include KDP ebook fixes that improve Kindle readability, reflow, and navigation.\n"
        )
    if include_citation_audit and include_voice_audit:
        audit_constraints += (
            "- Prioritize critical citation issues over cosmetic voice tweaks.\n"
        )
    return f"""You are revising my LaTeX book manuscript.

Start with `{book_entry.name}` and use it as the source of truth for the manuscript structure.
Follow the included `.tex` files listed below as the working scope.

Editorial instructions:
{setup_prompt}

Files in scope:
{file_list}
{audit_blocks}
Task:
1. Read the manuscript files in scope.
2. Identify the concrete revisions needed to satisfy the editorial instructions.
3. Return a concise, implementation-ready change plan grouped by file or chapter.

Constraints:
- Do not edit files yet.
- Keep the plan actionable and specific.
- Preserve the existing LaTeX project structure.
{audit_constraints}"""


def build_scoring_prompt(
    *,
    book_entry: Path,
    files_in_scope: list[str],
    phase_name: str,
    previous_output_token: str | None = None,
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    manuscript_note = ""
    if previous_output_token:
        manuscript_note = (
            "\nContext from the immediately prior step:\n"
            f"{previous_output_token}\n"
        )

    return f"""You are evaluating the quality of my nonfiction LaTeX book manuscript.

Start with `{book_entry.name}` and use it as the source of truth for the manuscript structure.
Review the included `.tex` files listed below as the manuscript in scope.

Files in scope:
{file_list}
{manuscript_note}
Use this scoring rubric exactly:
{SCORING_RUBRIC}

Task:
1. Read the manuscript as it exists right now in the repository.
2. Score each rubric category on a 1-1000 scale.
3. Compute a weighted overall score on a 1-1000 scale using the percentages above.
4. Return only valid JSON with no surrounding commentary or markdown fences.

Output JSON schema:
{{
  "phase": "{phase_name}",
  "overall_score": 1,
  "rubric": [
    {{
      "name": "Clarity & Accessibility",
      "weight_percent": 15,
      "score": 1,
      "reason": "short justification"
    }}
  ],
  "summary": "2-4 sentence explanation of the score"
}}

Constraints:
- The overall score must be an integer from 1 to 1000.
- Each category score must be an integer from 1 to 1000.
- Include all 10 rubric categories with the exact names shown above.
- Base the evaluation on the manuscript's current contents, not on hypothetical future edits.
"""


def build_implementation_prompt(
    files_in_scope: list[str],
    *,
    include_citation_audit: bool,
    include_voice_audit: bool,
    include_kdp_ebook_audit: bool,
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    context_blocks = """
Before-revision score (for context on what to improve):
{{output:score_book_before}}
"""
    if include_citation_audit:
        context_blocks += """
Citation audit (apply critical items even if omitted from the plan):
{{output:audit_citations}}
"""
    if include_voice_audit:
        context_blocks += """
Human-voice audit (apply critical items even if omitted from the plan):
{{output:audit_human_voice}}
"""
    if include_kdp_ebook_audit:
        context_blocks += """
KDP ebook-readiness audit (apply critical items even if omitted from the plan):
{{output:audit_kdp_ebook}}
"""
    extra_notes = ""
    if include_citation_audit:
        extra_notes += """
- Apply citation fixes from the revision plan and citation audit.
- Keep `\\cite{...}` keys synchronized with `\\bibitem{...}` entries in `backmatter/references.tex`.
"""
    if include_voice_audit:
        extra_notes += """
- Apply human-voice fixes from the revision plan and voice audit.
- Preserve LaTeX callout environments; edit inner text only.
"""
    if include_kdp_ebook_audit:
        extra_notes += """
- Apply KDP ebook fixes from the revision plan and KDP audit.
- Rewrite print-only references and simplify layouts that are likely to break in reflowable Kindle output.
- When a table or comparison is not essential as a table, prefer a heading-plus-list or short prose alternative.
"""
    extra_notes += """
- If the revision plan omitted a critical item from an audit, still apply the audit fix.
"""
    return f"""Implement the revision plan directly in the repository now.

Files in scope:
{file_list}

Revision plan to implement:
{{{{previous_output}}}}
{context_blocks}
{extra_notes}
Constraints:
- Edit manuscript `.tex` files in scope unless an out-of-scope change is truly required.
- Preserve the author's voice unless the setup prompt explicitly asks for a stronger rewrite.
- Keep the LaTeX valid.
- Do not modify generated artifacts such as `main.pdf` or `book_tts.txt`.
- When finished, summarize the files changed and the main improvements made.
"""


def build_citation_audit_prompt(
    *,
    book_entry: Path,
    files_in_scope: list[str],
    skill_instructions: str,
    structural_report: str,
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    return f"""You are auditing citations and source accuracy in my LaTeX book manuscript.

Start with `{book_entry.name}` and review the included `.tex` files listed below.
Follow the project's citation skill exactly.

Files in scope:
{file_list}

Citation skill instructions:
{skill_instructions}

Structural citation check output (from scripts/check_citations.py):
{structural_report}

Task:
1. Review high-stakes empirical, medical, and quantitative claims against nearby `\\cite{{...}}` usage.
2. Prioritize `\\begin{{researchnotebox}}` blocks, statistics, safety claims, and technology accuracy claims.
3. Flag claim-to-source mismatches, missing citations, and orphan `\\bibitem` entries worth citing or removing.
4. Return a concise citation audit using the report format from the skill.

Constraints:
- Do not edit files yet.
- Do not invent DOIs, page numbers, or study results.
- Distinguish critical issues from suggestions.
- Base findings on the manuscript as it exists now in the repository.
"""


def build_voice_audit_prompt(
    *,
    book_entry: Path,
    files_in_scope: list[str],
    skill_instructions: str,
    structural_report: str,
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    return f"""You are auditing human voice and prose quality in my LaTeX book manuscript.

Start with `{book_entry.name}` and review the included `.tex` files listed below.
Follow the project's humanize-book-voice skill exactly.

Files in scope:
{file_list}

Human-voice skill instructions:
{skill_instructions}

Structural voice check output (from scripts/check_ai_voice.py):
{structural_report}

Task:
1. Read flagged passages aloud in your head; note where prose sounds robotic or generic.
2. Prioritize rhythm, transitions, specificity, and over-balanced phrasing.
3. Flag AI tells without weakening citations, safety notes, or evidence tiers.
4. Return a concise voice audit using the report format from the skill.

Constraints:
- Do not edit files yet.
- Do not invent author memoir or personal anecdotes.
- Preserve LaTeX callout environments; suggest inner-text edits only.
- Distinguish critical issues from suggestions.
- Base findings on the manuscript as it exists now in the repository.
"""


def build_kdp_audit_prompt(
    *,
    book_entry: Path,
    files_in_scope: list[str],
) -> str:
    file_list = "\n".join(f"- {item}" for item in files_in_scope)
    return f"""You are auditing my LaTeX book manuscript for Kindle Direct Publishing (KDP) ebook readiness.

Start with `{book_entry.name}` and review the included `.tex` files listed below.

Files in scope:
{file_list}

KDP ebook guidance:
{KDP_EBOOK_GUIDANCE}

Task:
1. Find print-first or layout-dependent writing that should be rewritten for a reflowable ebook.
2. Prioritize wide tables, side-by-side layouts, overlong front matter, navigation friction, and references to page-based reading.
3. Flag sections that are likely to render awkwardly on Kindle screens and suggest the simplest manuscript-level fix.
4. Return a concise audit with two sections: `Critical issues` and `Suggestions`.

Constraints:
- Do not edit files yet.
- Focus on manuscript and LaTeX-structure issues that materially affect Kindle reader experience.
- Prefer fixes that keep the book readable in both source form and ebook output.
- Base findings on the manuscript as it exists now in the repository.
"""


def resolve_output_dir(cli_output_dir: Path | None) -> Path:
    if cli_output_dir is not None:
        return cli_output_dir.resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (ROOT / "codex_runs" / f"book-revision-{stamp}").resolve()


def build_chain(
    *,
    setup_prompt: str,
    book_entry: Path,
    workspace: Path,
    output_dir: Path,
    model: str | None,
    include_citations: bool,
    citation_skill: str,
    structural_citation_report: str,
    include_human_voice: bool,
    voice_skill: str,
    structural_voice_report: str,
    include_kdp_ebook: bool,
) -> dict[str, object]:
    files = discover_tex_files(book_entry)
    files_in_scope = relative_list(files, workspace=workspace)

    steps: list[dict[str, str]] = [
        {
            "name": "score_book_before",
            "prompt": build_scoring_prompt(
                book_entry=book_entry,
                files_in_scope=files_in_scope,
                phase_name="before",
            ),
        },
    ]

    if include_citations:
        steps.append(
            {
                "name": "audit_citations",
                "prompt": build_citation_audit_prompt(
                    book_entry=book_entry,
                    files_in_scope=files_in_scope,
                    skill_instructions=citation_skill,
                    structural_report=structural_citation_report,
                ),
            }
        )

    if include_human_voice:
        steps.append(
            {
                "name": "audit_human_voice",
                "prompt": build_voice_audit_prompt(
                    book_entry=book_entry,
                    files_in_scope=files_in_scope,
                    skill_instructions=voice_skill,
                    structural_report=structural_voice_report,
                ),
            }
        )

    if include_kdp_ebook:
        steps.append(
            {
                "name": "audit_kdp_ebook",
                "prompt": build_kdp_audit_prompt(
                    book_entry=book_entry,
                    files_in_scope=files_in_scope,
                ),
            }
        )

    steps.extend(
        [
            {
                "name": "review_book",
                "prompt": build_review_prompt(
                    setup_prompt=setup_prompt,
                    book_entry=book_entry,
                    files_in_scope=files_in_scope,
                    include_citation_audit=include_citations,
                    include_voice_audit=include_human_voice,
                    include_kdp_ebook_audit=include_kdp_ebook,
                ),
            },
            {
                "name": "implement_revisions",
                "prompt": build_implementation_prompt(
                    files_in_scope,
                    include_citation_audit=include_citations,
                    include_voice_audit=include_human_voice,
                    include_kdp_ebook_audit=include_kdp_ebook,
                ),
            },
            {
                "name": "score_book_after",
                "prompt": build_scoring_prompt(
                    book_entry=book_entry,
                    files_in_scope=files_in_scope,
                    phase_name="after",
                    previous_output_token="{{previous_output}}",
                ),
            },
        ]
    )

    chain: dict[str, object] = {
        "continue_session": True,
        "full_auto": True,
        "output_dir": str(output_dir),
        "steps": steps,
    }
    if model:
        chain["model"] = model
    return chain


def write_chain_file(chain: dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    chain_path = output_dir / "generated_book_revision_chain.json"
    chain_path.write_text(json.dumps(chain, indent=2) + "\n", encoding="utf-8")
    return chain_path


def extract_json_object(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates.extend(match.group(1).strip() for match in JSON_BLOCK_RE.finditer(text))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise ValueError("Could not parse a JSON object from the scoring output.")


def load_score_from_step(output_dir: Path, step_name: str) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing chain summary: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    steps = summary.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError(f"Invalid summary format in {summary_path}")

    for step in steps:
        if not isinstance(step, dict) or step.get("name") != step_name:
            continue
        last_message_path = step.get("last_message_path")
        if not isinstance(last_message_path, str) or not last_message_path:
            raise ValueError(f"Missing last_message_path for step {step_name}")
        output_text = Path(last_message_path).read_text(encoding="utf-8")
        return extract_json_object(output_text)

    raise ValueError(f"Could not find step {step_name} in {summary_path}")


def append_stable_score_report(report: dict[str, Any]) -> Path:
    stable_report_path = ROOT / "book_scores.json"
    history: list[dict[str, Any]]

    if stable_report_path.is_file():
        try:
            existing = json.loads(stable_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None

        if isinstance(existing, list):
            history = existing
        elif isinstance(existing, dict):
            history = [existing]
        else:
            history = []
    else:
        history = []

    history.append(report)
    stable_report_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return stable_report_path


def write_score_report(output_dir: Path, before: dict[str, Any], after: dict[str, Any]) -> Path:
    report = {
        "before": before,
        "after": after,
        "delta": None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(output_dir),
    }

    before_score = before.get("overall_score")
    after_score = after.get("overall_score")
    if isinstance(before_score, int) and isinstance(after_score, int):
        report["delta"] = after_score - before_score

    report_path = output_dir / "book_scores.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    append_stable_score_report(report)
    return report_path


def write_dry_run_score_report(output_dir: Path) -> Path:
    report = {
        "before": {"phase": "before", "overall_score": None, "summary": "dry-run placeholder"},
        "after": {"phase": "after", "overall_score": None, "summary": "dry-run placeholder"},
        "delta": None,
        "note": "Scores are not available in --dry-run mode because Codex was not executed.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(output_dir),
    }
    report_path = output_dir / "book_scores.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    append_stable_score_report(report)
    return report_path


def format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def detect_chain_progress(output_dir: Path) -> str | None:
    step_dirs: list[tuple[int, str, Path]] = []
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        match = STEP_DIR_RE.match(child.name)
        if not match:
            continue
        step_dirs.append((int(match.group(1)), match.group(2), child))

    if not step_dirs:
        return None

    _, raw_name, step_dir = max(step_dirs, key=lambda item: item[0])
    step_name = raw_name.replace("-", " ")
    last_message_path = step_dir / "last_message.txt"
    prompt_path = step_dir / "prompt.txt"

    if last_message_path.is_file() and last_message_path.stat().st_size > 0:
        return f"latest completed step looks like '{step_name}'"
    if prompt_path.is_file():
        return f"currently working on '{step_name}'"
    return f"latest known step is '{step_name}'"


def run_with_status_updates(
    command: list[str],
    *,
    cwd: Path,
    output_dir: Path,
    interval_seconds: int = 30,
) -> int:
    start = time.monotonic()
    next_update = start + interval_seconds
    proc = subprocess.Popen(command, cwd=cwd)

    while True:
        return_code = proc.poll()
        if return_code is not None:
            return return_code

        now = time.monotonic()
        if now >= next_update:
            elapsed = format_elapsed(now - start)
            progress = detect_chain_progress(output_dir)
            if progress:
                print(f"[status] Still running after {elapsed}; {progress}.", flush=True)
            else:
                print(
                    f"[status] Still running after {elapsed}; waiting for Codex to finish the current step.",
                    flush=True,
                )
            next_update += interval_seconds

        time.sleep(1)


def main() -> int:
    args = parse_args()

    if not CHAIN_RUNNER.is_file():
        raise SystemExit(f"Missing chain runner: {CHAIN_RUNNER}")

    workspace = args.workspace.resolve()
    setup_prompt_path = args.setup_prompt.resolve()
    book_entry = args.book_entry.resolve()
    output_dir = resolve_output_dir(args.output_dir)

    if not book_entry.is_file():
        raise SystemExit(f"Book entry file not found: {book_entry}")

    setup_prompt = load_prompt_text(setup_prompt_path)
    if args.kdp_ebook:
        setup_prompt = f"{setup_prompt}\n\n{KDP_EBOOK_GUIDANCE.strip()}"
    references_path = args.references.resolve()
    include_citations = not args.skip_citations
    include_human_voice = not args.skip_human_voice
    structural_citation_report = ""
    structural_voice_report = ""

    output_dir.mkdir(parents=True, exist_ok=True)

    if include_citations:
        citation_skill = load_citation_skill_text()
        citation_result, structural_citation_report = run_structural_citation_check(
            workspace=workspace,
            references=references_path,
        )
        preflight_path = output_dir / "citation_check_before.txt"
        preflight_path.write_text(structural_citation_report + "\n", encoding="utf-8")
        print(f"Citation pre-flight: {preflight_path}", flush=True)
        print(structural_citation_report, flush=True)
        if not citation_result.ok:
            print(
                "Fix undefined or duplicate citation keys before running the revision chain, "
                "or rerun with --skip-citations.",
                file=sys.stderr,
            )
            return 1
    else:
        citation_skill = ""

    if include_human_voice:
        voice_skill = load_voice_skill_text()
        voice_result, structural_voice_report = run_structural_voice_check(
            workspace=workspace,
        )
        voice_preflight_path = output_dir / "voice_check_before.txt"
        voice_preflight_path.write_text(structural_voice_report + "\n", encoding="utf-8")
        print(f"Voice pre-flight: {voice_preflight_path}", flush=True)
        print(structural_voice_report, flush=True)
        if not voice_result.ok:
            print(
                "Voice pre-flight found hard issues (see above). Continuing anyway; "
                "the audit step should address them.",
                flush=True,
            )
    else:
        voice_skill = ""

    chain = build_chain(
        setup_prompt=setup_prompt,
        book_entry=book_entry,
        workspace=workspace,
        output_dir=output_dir,
        model=args.model,
        include_citations=include_citations,
        citation_skill=citation_skill,
        structural_citation_report=structural_citation_report,
        include_human_voice=include_human_voice,
        voice_skill=voice_skill,
        structural_voice_report=structural_voice_report,
        include_kdp_ebook=args.kdp_ebook,
    )
    chain_path = write_chain_file(chain, output_dir)

    command = [
        sys.executable,
        str(CHAIN_RUNNER),
        str(chain_path),
        "--workspace",
        str(workspace),
    ]
    if args.dry_run:
        command.append("--dry-run")

    print(
        f"Starting Codex revision chain with model {args.model}. "
        f"Status updates will print every 30s. Artifacts: {output_dir}",
        flush=True,
    )
    return_code = run_with_status_updates(command, cwd=workspace, output_dir=output_dir)
    if return_code == 0:
        if args.dry_run:
            score_report_path = write_dry_run_score_report(output_dir)
        else:
            before_score = load_score_from_step(output_dir, "score_book_before")
            after_score = load_score_from_step(output_dir, "score_book_after")
            score_report_path = write_score_report(output_dir, before_score, after_score)
        if include_citations and not args.dry_run:
            post_result, post_report = run_structural_citation_check(
                workspace=workspace,
                references=references_path,
            )
            postflight_path = output_dir / "citation_check_after.txt"
            postflight_path.write_text(post_report + "\n", encoding="utf-8")
            print(f"Citation post-check: {postflight_path}", flush=True)
            print(post_report, flush=True)
            if not post_result.ok:
                print(
                    "Revision chain finished, but post-run citation check failed.",
                    file=sys.stderr,
                )
                return 1
        if include_human_voice and not args.dry_run:
            _voice_result, voice_post_report = run_structural_voice_check(
                workspace=workspace,
            )
            voice_postflight_path = output_dir / "voice_check_after.txt"
            voice_postflight_path.write_text(voice_post_report + "\n", encoding="utf-8")
            print(f"Voice post-check: {voice_postflight_path}", flush=True)
            print(voice_post_report, flush=True)
        print(f"Chain file: {chain_path}")
        print(f"Artifacts: {output_dir}")
        print(f"Scores: {score_report_path}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
