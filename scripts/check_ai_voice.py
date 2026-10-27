#!/usr/bin/env python3
"""
Scan LaTeX manuscript files for common AI-prose tells.

Reports:
  - AI vocabulary, throat-clearing phrases, template framing, overclaims
  - Repeated paragraph openings
  - Repeated words and phrases with reduction suggestions
  - High em-dash density
  - Stacked identical callout environments

Usage (from project root):
  python3 scripts/check_ai_voice.py
  python3 scripts/check_ai_voice.py --verbose
  python3 scripts/check_ai_voice.py --strict
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_DIRS = ("chapters", "backmatter", "frontmatter")
_SKIP_OPENING_SCAN = frozenset({"backmatter/references.tex"})

# (label, regex). Keep in sync with .cursor/skills/humanize-book-voice/SKILL.md
_VOCAB_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Furthermore", re.compile(r"\bFurthermore\b")),
    ("Moreover", re.compile(r"\bMoreover\b")),
    ("Additionally", re.compile(r"\bAdditionally\b")),
    ("Consequently", re.compile(r"\bConsequently\b")),
    ("Subsequently", re.compile(r"\bSubsequently\b")),
    ("Nevertheless", re.compile(r"\bNevertheless\b")),
    ("Accordingly", re.compile(r"\bAccordingly\b")),
    ("In conclusion", re.compile(r"\bIn conclusion\b", re.I)),
    ("It's worth noting", re.compile(r"\bIt['’]s worth noting\b", re.I)),
    ("It is worth noting", re.compile(r"\bIt is worth noting\b", re.I)),
    ("delve", re.compile(r"\bdelve\b", re.I)),
    ("landscape", re.compile(r"\blandscape\b", re.I)),
    ("robust", re.compile(r"\brobust\b", re.I)),
    ("comprehensive", re.compile(r"\bcomprehensive\b", re.I)),
    ("pivotal", re.compile(r"\bpivotal\b", re.I)),
    ("crucial", re.compile(r"\bcrucial\b", re.I)),
    ("leverage", re.compile(r"\bleverage\b", re.I)),
    ("utilize", re.compile(r"\butilize\b", re.I)),
    ("harness", re.compile(r"\bharness\b", re.I)),
    ("multifaceted", re.compile(r"\bmultifaceted\b", re.I)),
    ("tapestry", re.compile(r"\btapestry\b", re.I)),
    ("game-changer", re.compile(r"\bgame[- ]changer\b", re.I)),
    ("facilitate", re.compile(r"\bfacilitate\b", re.I)),
    ("elucidate", re.compile(r"\belucidate\b", re.I)),
    ("paradigm", re.compile(r"\bparadigm\b", re.I)),
    ("myriad", re.compile(r"\bmyriad\b", re.I)),
    ("seamless", re.compile(r"\bseamless\b", re.I)),
    ("underscore", re.compile(r"\bunderscores?\b", re.I)),
    ("testament to", re.compile(r"\btestament to\b", re.I)),
    ("navigate the", re.compile(r"\bnavigate the\b", re.I)),
    ("holistic", re.compile(r"\bholistic\b", re.I)),
    ("cutting-edge", re.compile(r"\bcutting[- ]edge\b", re.I)),
    ("revolutioniz", re.compile(r"\brevolutioniz\w*\b", re.I)),
    ("transformative", re.compile(r"\btransformative\b", re.I)),
)

_THROAT_CLEARING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("It is important to note", re.compile(r"\bIt is important to note\b", re.I)),
    ("It's important to note", re.compile(r"\bIt['’]s important to note\b", re.I)),
    ("It bears mentioning", re.compile(r"\bIt bears mentioning\b", re.I)),
    ("It is worth mentioning", re.compile(r"\bIt is worth mentioning\b", re.I)),
    ("Generally speaking", re.compile(r"\bGenerally speaking\b", re.I)),
    ("In many cases", re.compile(r"\bIn many cases\b", re.I)),
    ("One might argue", re.compile(r"\bOne might argue\b", re.I)),
    ("It could be argued", re.compile(r"\bIt could be argued\b", re.I)),
    ("This chapter aims", re.compile(r"\bThis chapter aims\b", re.I)),
    ("In today's", re.compile(r"\bIn today['’]s\b", re.I)),
    ("ever-evolving", re.compile(r"\bever[- ]evolving\b", re.I)),
    ("fast-paced world", re.compile(r"\bfast[- ]paced world\b", re.I)),
    ("When it comes to", re.compile(r"\bWhen it comes to\b", re.I)),
    ("At the end of the day", re.compile(r"\bAt the end of the day\b", re.I)),
    ("That being said", re.compile(r"\bThat being said\b", re.I)),
    ("double-edged sword", re.compile(r"\bdouble[- ]edged sword\b", re.I)),
    (
        "plays a crucial/vital/pivotal role",
        re.compile(r"\bplays a (?:crucial|vital|pivotal) role\b", re.I),
    ),
    ("In order to", re.compile(r"\bIn order to\b", re.I)),
    ("underscores the importance", re.compile(r"\bunderscores the importance\b", re.I)),
    ("transformative experience", re.compile(r"\btransformative experience\b", re.I)),
    ("holistic approach", re.compile(r"\bholistic approach\b", re.I)),
    ("In the realm of", re.compile(r"\bIn the realm of\b", re.I)),
    ("To summarize", re.compile(r"\bTo summarize\b", re.I)),
)

_TEMPLATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("In plain language", re.compile(r"\bIn plain language\b", re.I)),
    ("That is a useful", re.compile(r"\bThat is a useful\b", re.I)),
    ("This chapter lives outside", re.compile(r"\bThis chapter lives outside\b", re.I)),
    ("For many beginners", re.compile(r"\bFor many beginners\b", re.I)),
    ("The key takeaway is", re.compile(r"\bThe key takeaway is\b", re.I)),
    ("This chapter will explore", re.compile(r"\bThis chapter will explore\b", re.I)),
)

_CONTRAST_TEMPLATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("It's not X, it's Y", re.compile(r"\bIt(?:'|’)s not\b[^.!?;\n]{1,80}\bit(?:'|’)s\b", re.I)),
    ("This isn't X. It's Y", re.compile(r"\bThis (?:isn(?:'|’)t|is not)\b[^.!?;\n]{1,80}\bIt(?:'|’)s\b", re.I)),
    ("not just X, but Y", re.compile(r"\bnot just\b[^.!?;\n]{1,80}\bbut\b", re.I)),
)

_OVERCLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("This isn't speculation", re.compile(r"\bThis isn['’]t speculation\b", re.I)),
    ("This is not speculation", re.compile(r"\bThis is not speculation\b", re.I)),
    ("The neuroscience is clear", re.compile(r"\bThe neuroscience is clear\b", re.I)),
    ("proven forever", re.compile(r"\bproven forever\b", re.I)),
    ("fully proven", re.compile(r"\bfully proven\b", re.I)),
    ("guaranteed to", re.compile(r"\bguaranteed to\b", re.I)),
    ("without a doubt", re.compile(r"\bwithout a doubt\b", re.I)),
)

_PATTERN_GROUPS: tuple[tuple[str, int, tuple[tuple[str, re.Pattern[str]], ...]], ...] = (
    ("AI vocabulary", 2, _VOCAB_PATTERNS),
    ("Throat-clearing", 1, _THROAT_CLEARING_PATTERNS),
    ("Template framing", 2, _TEMPLATE_PATTERNS),
    ("Contrast templates", 2, _CONTRAST_TEMPLATE_PATTERNS),
    ("Overclaim", 1, _OVERCLAIM_PATTERNS),
)

_CALLOUT_RE = re.compile(r"\\begin\{([a-z]+box)\}")
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z@]+(\[[^\]]*\])?(\{[^{}]*\})*")
_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
_COMMON_WORDS = frozenset(
    {
        "a",
        "about",
        "all",
        "also",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "because",
        "but",
        "by",
        "can",
        "do",
        "does",
        "even",
        "every",
        "for",
        "from",
        "get",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "may",
        "more",
        "most",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "them",
        "there",
        "they",
        "this",
        "than",
        "to",
        "what",
        "with",
        "up",
        "use",
        "using",
        "when",
        "while",
        "you",
        "your",
    }
)
_DOMAIN_CORE_WORDS = frozenset(
    {
        "argument",
        "assumption",
        "evidence",
        "hypothesis",
        "objection",
        "probability",
        "simulation",
    }
)
_COMMON_PHRASES = frozenset(
    {
        "a few",
        "and the",
        "for the",
        "in the",
        "is often",
        "is still",
        "it is",
        "of the",
        "one of the",
        "reference class",
        "simulation hypothesis",
        "the argument",
        "the claim",
        "the first",
        "the next",
        "the same",
        "the simulation",
        "to the",
        "you can",
        "you do not",
    }
)
_WORD_VARIANTS: dict[str, str] = {
    "actually": "cut it when it adds no contrast, or replace it with a more specific claim",
    "better": "swap some instances for a more concrete comparison, or name the tradeoff directly",
    "cleaner": "replace a few uses with specifics such as quieter, simpler, lower-friction, or less distracting",
    "gentle": "vary with soft, light, calm, low-stimulation, or remove it where context already implies softness",
    "help": "alternate with support, reduce friction, make easier, or rewrite the sentence around the concrete action",
    "important": "replace with the exact reason something matters, or cut the emphasis entirely",
    "practice": "alternate with routine, habit, training, or name the exact exercise being described",
    "readers": "sometimes switch to people, beginners, or the specific type of reader in context",
    "simple": "vary with clear, low-friction, basic, or strip the modifier if the sentence already feels plain",
    "technology": "replace some mentions with tool, device, app, setup, or the specific tool being discussed",
    "useful": "replace with the precise value delivered, such as faster capture, less friction, or better recall",
}
_PHRASE_VARIANTS: dict[str, str] = {
    "for most readers": "replace some uses with a more specific audience label or simply cut the framing when the sentence still works without it",
    "the goal is": "rewrite some instances as direct statements of the goal instead of announcing it first",
    "you do not need": "vary with you can skip, most people can do without, or state the simpler default directly",
    "if you": "combine or restructure nearby advice so fewer consecutive sentences start with conditional coaching",
    "the hypothesis": "sometimes name the exact claim instead of repeating the label",
    "reference class": "alternate with the group being counted, or name that group directly",
}


@dataclass
class PatternHit:
    label: str
    category: str
    count: int
    locations: list[str] = field(default_factory=list)


@dataclass
class RepetitionHit:
    text: str
    count: int
    suggestion: str


@dataclass
class VoiceCheckResult:
    ok: bool
    files_scanned: int
    word_count: int
    pattern_hits: list[PatternHit] = field(default_factory=list)
    repeated_words: list[RepetitionHit] = field(default_factory=list)
    repeated_phrases: list[RepetitionHit] = field(default_factory=list)
    repeated_openings: list[str] = field(default_factory=list)
    em_dash_per_1k: float = 0.0
    stacked_callouts: list[str] = field(default_factory=list)
    hard_issues: list[str] = field(default_factory=list)

    @property
    def glue_hits(self) -> list[PatternHit]:
        """Backward-compatible alias for vocabulary hits only."""
        return [hit for hit in self.pattern_hits if hit.category == "AI vocabulary"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan LaTeX manuscript files for common AI-prose tells.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root (default: repo root).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include every pattern location in the report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when hard issues are found.",
    )
    parser.add_argument(
        "--glue-threshold",
        type=int,
        default=2,
        metavar="N",
        help="Flag AI vocabulary appearing N+ times in one file (default: 2).",
    )
    parser.add_argument(
        "--em-dash-threshold",
        type=float,
        default=8.0,
        metavar="N",
        help="Warn when em dashes exceed N per 1000 words (default: 8).",
    )
    parser.add_argument(
        "--top-words",
        type=int,
        default=15,
        metavar="N",
        help="Show up to N repeated content words (default: 15).",
    )
    parser.add_argument(
        "--top-phrases",
        type=int,
        default=15,
        metavar="N",
        help="Show up to N repeated phrases (default: 15).",
    )
    parser.add_argument(
        "--min-word-count",
        type=int,
        default=6,
        metavar="N",
        help="Only report repeated words seen at least N times (default: 6).",
    )
    parser.add_argument(
        "--min-phrase-count",
        type=int,
        default=3,
        metavar="N",
        help="Only report repeated phrases seen at least N times (default: 3).",
    )
    return parser.parse_args()


def discover_tex_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirname in DEFAULT_SCAN_DIRS:
        directory = root / dirname
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.tex")))
    return files


def strip_latex_for_analysis(text: str) -> str:
    text = re.sub(r"(?m)^%.*$", "", text)
    text = _LATEX_CMD_RE.sub(" ", text)
    text = text.replace("---", "—")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def paragraph_openings(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    openings: list[str] = []
    for paragraph in paragraphs:
        plain = strip_latex_for_analysis(paragraph)
        words = _WORD_RE.findall(plain)
        if words:
            openings.append(words[0].casefold())
    return openings


def count_em_dashes(text: str) -> int:
    return text.count("---") + text.count("—") + text.count("--")


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(strip_latex_for_analysis(text)))


def tokenize_words(text: str) -> list[str]:
    plain = strip_latex_for_analysis(text).casefold()
    return _WORD_RE.findall(plain)


def _suggest_for_word(word: str) -> str:
    custom = _WORD_VARIANTS.get(word)
    if custom:
        return custom
    return "replace some instances with a more concrete noun or verb, or cut the word where the sentence still works without it"


def _suggest_for_phrase(phrase: str) -> str:
    custom = _PHRASE_VARIANTS.get(phrase)
    if custom:
        return custom
    return "rewrite a few instances with a different sentence shape or fold the idea into nearby prose instead of repeating the same phrase"


def collect_repeated_words(
    texts: list[str],
    *,
    min_count: int,
    limit: int,
) -> list[RepetitionHit]:
    counter: collections.Counter[str] = collections.Counter()
    for text in texts:
        for word in tokenize_words(text):
            if (
                len(word) < 4
                or word in _COMMON_WORDS
                or word in _DOMAIN_CORE_WORDS
            ):
                continue
            counter[word] += 1

    results: list[RepetitionHit] = []
    for word, count in counter.most_common():
        if count < min_count:
            continue
        results.append(
            RepetitionHit(
                text=word,
                count=count,
                suggestion=_suggest_for_word(word),
            )
        )
        if len(results) >= limit:
            break
    return results


def collect_repeated_phrases(
    texts: list[str],
    *,
    min_count: int,
    limit: int,
) -> list[RepetitionHit]:
    counter: collections.Counter[str] = collections.Counter()

    for text in texts:
        plain = strip_latex_for_analysis(text).casefold()
        for sentence in _SENTENCE_SPLIT_RE.split(plain):
            words = _WORD_RE.findall(sentence)
            for size in (2, 3, 4):
                if len(words) < size:
                    continue
                for i in range(len(words) - size + 1):
                    phrase_words = words[i : i + size]
                    phrase = " ".join(phrase_words)
                    if phrase in _COMMON_PHRASES:
                        continue
                    if all(word in _COMMON_WORDS for word in phrase_words):
                        continue
                    if len(phrase_words[-1]) < 3:
                        continue
                    counter[phrase] += 1

    results: list[RepetitionHit] = []
    seen_prefixes: set[str] = set()
    for phrase, count in counter.most_common():
        if count < min_count:
            continue
        # Skip shorter phrases when a stronger longer phrase with the same opening is already reported.
        prefix = " ".join(phrase.split()[:3])
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        results.append(
            RepetitionHit(
                text=phrase,
                count=count,
                suggestion=_suggest_for_phrase(phrase),
            )
        )
        if len(results) >= limit:
            break
    return results


def _scan_patterns(
    text: str,
    rel: Path,
    *,
    vocab_threshold: int,
) -> list[PatternHit]:
    hits: list[PatternHit] = []
    hit_index: dict[tuple[str, str], PatternHit] = {}

    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, default_threshold, patterns in _PATTERN_GROUPS:
            threshold = (
                vocab_threshold if category == "AI vocabulary" else default_threshold
            )
            for label, pattern in patterns:
                if not pattern.search(line):
                    continue
                key = (category, label)
                existing = hit_index.get(key)
                if existing is None:
                    existing = PatternHit(label=label, category=category, count=0)
                    hit_index[key] = existing
                    hits.append(existing)
                existing.count += len(pattern.findall(line))
                existing.locations.append(f"{rel}:{line_no}")

    return [hit for hit in hits if hit.count >= _threshold_for_hit(hit, vocab_threshold)]


def _threshold_for_hit(hit: PatternHit, vocab_threshold: int) -> int:
    for category, default_threshold, _patterns in _PATTERN_GROUPS:
        if hit.category == category:
            if category == "AI vocabulary":
                return vocab_threshold
            return default_threshold
    return 1


def scan_file(
    path: Path,
    *,
    root: Path,
    vocab_threshold: int,
) -> tuple[int, list[PatternHit], list[str], int, list[str]]:
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="replace")
    words = count_words(text)
    em_dashes = count_em_dashes(text)

    pattern_hits = _scan_patterns(text, rel, vocab_threshold=vocab_threshold)

    openings = paragraph_openings(text)
    repeated: list[str] = []
    rel_str = str(rel).replace("\\", "/")
    if rel_str not in _SKIP_OPENING_SCAN:
        streak = 1
        for i in range(1, len(openings)):
            if openings[i] == openings[i - 1] and openings[i] not in {
                "",
                "the",
                "this",
                "a",
                "if",
                "suppose",
                "use",
            }:
                streak += 1
                if streak == 3:
                    repeated.append(
                        f"{rel}: paragraphs {i - 1}-{i + 1} start with '{openings[i]}'"
                    )
            else:
                streak = 1

    stacked_callouts: list[str] = []
    callout_lines: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _CALLOUT_RE.search(line)
        if match:
            callout_lines.append((line_no, match.group(1)))
    streak = 1
    for i in range(1, len(callout_lines)):
        if callout_lines[i][1] == callout_lines[i - 1][1]:
            streak += 1
            if streak == 4:
                stacked_callouts.append(
                    f"{rel}: {callout_lines[i][1]} repeated 4+ times "
                    f"(from line {callout_lines[i - 3][0]})"
                )
        else:
            streak = 1

    return words, pattern_hits, repeated, em_dashes, stacked_callouts


def check_ai_voice(
    *,
    root: Path | None = None,
    glue_threshold: int = 2,
    em_dash_threshold: float = 8.0,
    top_words: int = 15,
    top_phrases: int = 15,
    min_word_count: int = 6,
    min_phrase_count: int = 3,
) -> VoiceCheckResult:
    root = (root or ROOT).resolve()
    tex_files = discover_tex_files(root)

    total_words = 0
    total_em_dashes = 0
    all_hits: dict[tuple[str, str], PatternHit] = {}
    all_texts: list[str] = []
    repeated_openings: list[str] = []
    stacked_callouts: list[str] = []

    for path in tex_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        all_texts.append(text)
        words, pattern_hits, repeated, em_dashes, stacked = scan_file(
            path,
            root=root,
            vocab_threshold=glue_threshold,
        )
        total_words += words
        total_em_dashes += em_dashes
        repeated_openings.extend(repeated)
        stacked_callouts.extend(stacked)
        for hit in pattern_hits:
            key = (hit.category, hit.label)
            existing = all_hits.get(key)
            if existing is None:
                all_hits[key] = PatternHit(
                    label=hit.label,
                    category=hit.category,
                    count=hit.count,
                    locations=list(hit.locations),
                )
            else:
                existing.count += hit.count
                existing.locations.extend(hit.locations)

    em_dash_per_1k = (total_em_dashes * 1000.0 / total_words) if total_words else 0.0
    hard_issues: list[str] = []
    if em_dash_per_1k >= em_dash_threshold:
        hard_issues.append(
            f"Em-dash density high: {em_dash_per_1k:.1f} per 1000 words "
            f"(threshold {em_dash_threshold})"
        )
    hard_issues.extend(stacked_callouts)

    pattern_hits = sorted(
        all_hits.values(),
        key=lambda hit: (hit.category, -hit.count, hit.label),
    )
    repeated_words = collect_repeated_words(
        all_texts,
        min_count=min_word_count,
        limit=top_words,
    )
    repeated_phrases = collect_repeated_phrases(
        all_texts,
        min_count=min_phrase_count,
        limit=top_phrases,
    )

    return VoiceCheckResult(
        ok=not hard_issues,
        files_scanned=len(tex_files),
        word_count=total_words,
        pattern_hits=pattern_hits,
        repeated_words=repeated_words,
        repeated_phrases=repeated_phrases,
        repeated_openings=repeated_openings,
        em_dash_per_1k=em_dash_per_1k,
        stacked_callouts=stacked_callouts,
        hard_issues=hard_issues,
    )


def format_voice_report(result: VoiceCheckResult, *, verbose: bool = False) -> str:
    lines = [
        f"Scanned {result.files_scanned} .tex files",
        f"Approximate words analyzed: {result.word_count}",
        f"Em dashes per 1000 words: {result.em_dash_per_1k:.1f}",
        "",
    ]

    if result.pattern_hits:
        current_category: str | None = None
        for hit in result.pattern_hits:
            if hit.category != current_category:
                current_category = hit.category
                lines.append(f"{current_category} (threshold met):")
            lines.append(f"  {hit.label}: {hit.count}")
            if verbose:
                for location in hit.locations:
                    lines.append(f"    {location}")
        lines.append("")

    if result.repeated_words:
        lines.append("Repeated words to vary:")
        for hit in result.repeated_words:
            lines.append(f"  {hit.text}: {hit.count} -- {hit.suggestion}")
        lines.append("")

    if result.repeated_phrases:
        lines.append("Repeated phrases to vary:")
        for hit in result.repeated_phrases:
            lines.append(f"  {hit.text}: {hit.count} -- {hit.suggestion}")
        lines.append("")

    if result.repeated_openings:
        lines.append("Repeated paragraph openings (review; may be intentional in examples):")
        for item in result.repeated_openings:
            lines.append(f"  {item}")
        lines.append("")

    if result.stacked_callouts:
        lines.append("Stacked callout environments:")
        for item in result.stacked_callouts:
            lines.append(f"  {item}")
        lines.append("")

    if result.hard_issues:
        lines.append("Hard issues:")
        for item in result.hard_issues:
            lines.append(f"  {item}")
        lines.append("")

    if result.ok and not result.pattern_hits:
        lines.append("Voice check passed (no hard issues or flagged patterns).")
    elif result.ok:
        lines.append("Voice check passed (no hard issues). Review pattern hits above.")
    else:
        lines.append("Voice check found hard issues (see above).")

    return "\n".join(lines)


def print_voice_report(
    result: VoiceCheckResult,
    *,
    verbose: bool = False,
    strict: bool = False,
) -> int:
    print(format_voice_report(result, verbose=verbose))
    if strict and not result.ok:
        print("Voice check failed in --strict mode.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    result = check_ai_voice(
        root=root,
        glue_threshold=args.glue_threshold,
        em_dash_threshold=args.em_dash_threshold,
        top_words=args.top_words,
        top_phrases=args.top_phrases,
        min_word_count=args.min_word_count,
        min_phrase_count=args.min_phrase_count,
    )
    return print_voice_report(result, verbose=args.verbose, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
