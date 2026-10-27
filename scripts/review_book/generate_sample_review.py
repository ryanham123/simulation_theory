#!/usr/bin/env python3
"""
Generate a clearly disclosed sample review based on the local book text.

This script is intended for drafting/reviewing marketing copy, not for
impersonating a real customer. The output is labeled as a fictional example.

Usage (from project root):
  python3 scripts/review_book/generate_sample_review.py
  python3 scripts/review_book/generate_sample_review.py --rating 4 --persona beginner
  python3 scripts/review_book/generate_sample_review.py --output sample_review.txt
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from run_codex_prompt_chain import resolve_codex_bin

DEFAULT_BOOK_PATH = ROOT / "book_tts.txt"
DEFAULT_URL = "https://example.com/the-simulation-question/"
DEFAULT_HISTORY_PATH = ROOT / "sample_review_history.json"
FIREBASE_PROJECT_ID = "journeyhue"
FIRESTORE_COLLECTION = "book_reviews_simulation_question"
BOOK_SLUG = "simulation-question"

PERSONAS: dict[str, dict[str, str]] = {
    "beginner": {
        "label": "curious beginner",
        "hook": "Placeholder hook for a reader new to the simulation question.",
        "need": "beginner-friendly",
        "value": "Placeholder value for a clear first map of the claim.",
    },
    "science-curious": {
        "label": "science-curious reader",
        "hook": "Placeholder hook for a reader who wants the argument kept separate from hype.",
        "need": "grounded",
        "value": "Placeholder value for evidence notes and confidence levels.",
    },
    "skeptic": {
        "label": "skeptical reader",
        "hook": "Placeholder hook for a reader who wants the objections kept in view.",
        "need": "critical",
        "value": "Placeholder value for a chapter that takes objections seriously.",
    },
    "busy-reader": {
        "label": "busy reader looking for a short path",
        "hook": "Placeholder hook for a reader who wants the core path without the optional depth.",
        "need": "time-efficient",
        "value": "Placeholder value for a book that says what can be skipped.",
    },
    "philosophy-reader": {
        "label": "philosophy-minded reader",
        "hook": "Placeholder hook for a reader comparing this claim with older skeptical problems.",
        "need": "reflective",
        "value": "Placeholder value for keeping related ideas distinct.",
    },
    "culture-reader": {
        "label": "reader who met the idea through films and games",
        "hook": "Placeholder hook for a reader sorting the pop version from the argument.",
        "need": "contextual",
        "value": "Placeholder value for a culture chapter that does not let the metaphor take over.",
    },
    "cautious-reader": {
        "label": "reader wary of grand claims",
        "hook": "Placeholder hook for a reader who wants uncertainty handled without drama.",
        "need": "caution",
        "value": "Placeholder value for pacing and realistic expectations.",
    },
    "returning-reader": {
        "label": "reader returning to the simulation question",
        "hook": "Placeholder hook for a reader who wants a calmer second pass.",
        "need": "re-entry friendly",
        "value": "Placeholder value for fundamentals before optional depth.",
    },
    "argument-reader": {
        "label": "reader who already knows the trilemma",
        "hook": "Placeholder hook for a reader who wants the assumptions and the probability step unpacked.",
        "need": "next-step practical",
        "value": "Placeholder value for connecting the claim, the assumptions, and the objections.",
    },
}

TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("simulation hypothesis", re.compile(r"\bsimulation hypothesis\b", re.I)),
    ("ancestor simulation", re.compile(r"\bancestor simulations?\b", re.I)),
    ("reference class", re.compile(r"\breference class(?:es)?\b", re.I)),
    ("self-sampling", re.compile(r"\bself-sampling\b", re.I)),
    ("objections", re.compile(r"\bobjections?\b", re.I)),
    ("evidence", re.compile(r"\bevidence\b|\bresearch\b|\bconfidence\b", re.I)),
)

FIRST_NAMES: tuple[str, ...] = (
    "Alice",
    "Benjamin",
    "Charlotte",
    "Daniel",
    "Eleanor",
    "Frederick",
    "Grace",
    "Henry",
    "Isla",
    "James",
    "Lucy",
    "Matthew",
    "Nora",
    "Oliver",
    "Penelope",
    "Samuel",
    "Sophie",
    "Thomas",
    "Violet",
    "William",
)

LAST_NAMES: tuple[str, ...] = (
    "Anderson",
    "Bennett",
    "Carter",
    "Collins",
    "Dawson",
    "Ellis",
    "Foster",
    "Griffin",
    "Harrison",
    "Jenkins",
    "Mitchell",
    "Parker",
    "Reed",
    "Robinson",
    "Stewart",
    "Taylor",
    "Turner",
    "Walker",
    "Ward",
    "Wright",
)

REVIEWER_STYLES: dict[str, dict[str, tuple[str, ...] | str]] = {
    "measured": {
        "label": "measured and thoughtful",
        "bridge_options": (
            "Placeholder measured bridge.",
            "Placeholder measured bridge, alternate.",
            "Placeholder measured bridge, third.",
        ),
        "reflection_options": (
            "Placeholder measured reflection.",
            "Placeholder measured reflection, alternate.",
            "Placeholder measured reflection, third.",
        ),
        "closing_options": (
            "Placeholder measured closing.",
            "Placeholder measured closing, alternate.",
            "Placeholder measured closing, third.",
        ),
    },
    "enthusiastic": {
        "label": "enthusiastic but not hypey",
        "bridge_options": (
            "Placeholder enthusiastic bridge.",
            "Placeholder enthusiastic bridge, alternate.",
            "Placeholder enthusiastic bridge, third.",
        ),
        "reflection_options": (
            "Placeholder enthusiastic reflection.",
            "Placeholder enthusiastic reflection, alternate.",
            "Placeholder enthusiastic reflection, third.",
        ),
        "closing_options": (
            "Placeholder enthusiastic closing.",
            "Placeholder enthusiastic closing for a friend curious about the simulation question.",
            "Placeholder enthusiastic closing about sitting with the argument.",
        ),
    },
    "analytical": {
        "label": "analytical and detail-oriented",
        "bridge_options": (
            "Placeholder analytical bridge.",
            "Placeholder analytical bridge, alternate.",
            "Placeholder analytical bridge, third.",
        ),
        "reflection_options": (
            "Placeholder analytical reflection.",
            "Placeholder analytical reflection, alternate.",
            "Placeholder analytical reflection, third.",
        ),
        "closing_options": (
            "Placeholder analytical closing.",
            "Placeholder analytical closing, alternate.",
            "Placeholder analytical closing, third.",
        ),
    },
}

REVIEW_SHAPES: tuple[str, ...] = (
    "immediate_reaction",
    "specific_takeaway",
    "comparison",
    "personal_use_case",
    "slow_burn",
)

PERSONAL_CONTEXT_SNIPPETS: dict[str, tuple[str, ...]] = {
    "beginner": (
        "Placeholder note from a first-time reader.",
        "Placeholder note about starting with the core path.",
        "Placeholder note about skipping optional depth at first.",
        "Placeholder note about reading the claim before the probability step.",
    ),
    "science-curious": (
        "Placeholder note about separating evidence from speculation.",
        "Placeholder note about wanting a framework more than a slogan.",
        "Placeholder note about flagging confidence levels.",
        "Placeholder note about checking what a source can actually support.",
    ),
    "skeptic": (
        "Placeholder note about reading the objections first.",
        "Placeholder note about watching for claims that explain too much.",
        "Placeholder note about the simulator regress.",
        "Placeholder note about keeping designer analogies in their own section.",
    ),
    "busy-reader": (
        "Placeholder note about using the how-to-use chapter as a map.",
        "Placeholder note about finishing the core path on a short schedule.",
        "Placeholder note about leaving the optional chapters for later.",
        "Placeholder note about wanting one clear next step.",
    ),
    "philosophy-reader": (
        "Placeholder note about comparing the claim with older skepticism.",
        "Placeholder note about related ideas staying off the core path.",
        "Placeholder note about consciousness as a limit.",
        "Placeholder note about not collapsing distinct arguments into one.",
    ),
    "culture-reader": (
        "Placeholder note about films and games as a separate chapter.",
        "Placeholder note about AI as a different claim.",
        "Placeholder note about metaphor versus argument.",
        "Placeholder note about the idea's history before the movies.",
    ),
    "cautious-reader": (
        "Placeholder note about pacing.",
        "Placeholder note about uncertainty without drama.",
        "Placeholder note about what the book will not pretend to settle.",
        "Placeholder note about living with an open question.",
    ),
    "returning-reader": (
        "Placeholder note about a second pass through the assumptions.",
        "Placeholder note about wanting the fundamentals again.",
        "Placeholder note about optional depth after the core path.",
        "Placeholder note about a calmer re-entry.",
    ),
    "argument-reader": (
        "Placeholder note about the trilemma's assumptions.",
        "Placeholder note about reference classes.",
        "Placeholder note about a fragile probability.",
        "Placeholder note about connecting claim, evidence, and objection.",
    ),
}

OPENING_LINES: dict[str, tuple[str, ...]] = {
    "immediate_reaction": (
        "Placeholder opening for an immediate reaction.",
        "Placeholder opening for a first impression of the tone.",
        "Placeholder opening for how undramatic the claim is stated.",
    ),
    "specific_takeaway": (
        "Placeholder opening for a specific takeaway.",
        "Placeholder opening for a step that stayed with the reader.",
        "Placeholder opening for leaving with a method of reading, not a verdict.",
    ),
    "comparison": (
        "Placeholder opening comparing this book with other simulation-theory material.",
        "Placeholder opening about usability compared with slogan-driven versions.",
        "Placeholder opening about guidance rather than mythology.",
    ),
    "personal_use_case": (
        "Placeholder opening for an ordinary-week reading plan.",
        "Placeholder opening for testing the argument against the reader's own doubts.",
        "Placeholder opening for a use case that fits a short schedule.",
    ),
    "slow_burn": (
        "Placeholder opening for a slow start that later clicked.",
        "Placeholder opening for gradual trust in the structure.",
        "Placeholder opening for momentum in the later core chapters.",
    ),
}

TRANSITION_LINES: tuple[str, ...] = (
    "Placeholder transition toward a bookmarked section.",
    "Placeholder transition toward the strongest impression.",
    "Placeholder transition toward the sections actually marked.",
    "Placeholder transition toward the most usable material.",
    "Placeholder transition toward what lingered afterward.",
)

PRAISE_LINES: tuple[str, ...] = (
    "Placeholder praise for keeping the claim learnable.",
    "Placeholder praise for a human scale.",
    "Placeholder praise for usable reasoning.",
    "Placeholder praise for treating uncertainty as normal.",
    "Placeholder praise for not pretending every argument lands the same way.",
)

CRITIQUE_LINES: tuple[str, ...] = (
    "Placeholder critique about a dense stretch.",
    "Placeholder critique about detail that slowed the reading.",
    "Placeholder critique about an idea that could be shorter.",
    "Placeholder critique about a section that felt more like a study note.",
)

SOFT_CRITIQUE_LINES: tuple[str, ...] = (
    "Placeholder soft caveat.",
    "Placeholder note that the issue was small.",
    "Placeholder note that the issue did not end the reading.",
    "Placeholder note that the useful parts still outweighed it.",
)

TOPIC_SENTENCE_TEMPLATES: tuple[str, ...] = (
    "{bridge} {topic_phrase}.",
    "{transition} {topic_phrase}.",
    "Placeholder sentence highlighting {topic_phrase}.",
    "Placeholder sentence returning to {topic_phrase}.",
)

HEADLINE_TEMPLATES: dict[int, tuple[str, ...]] = {
    5: (
        "Placeholder five-star headline for {label}",
        "Placeholder five-star headline, alternate, for {label}",
        "Placeholder five-star headline, third",
        "Placeholder five-star headline, fourth",
    ),
    4: (
        "Placeholder four-star headline",
        "Placeholder four-star headline, alternate",
        "Placeholder four-star headline, third",
        "Placeholder four-star headline, fourth",
    ),
    3: (
        "Placeholder three-star headline",
        "Placeholder three-star headline, alternate",
        "Placeholder three-star headline, third",
    ),
    2: (
        "Placeholder two-star headline",
        "Placeholder two-star headline, alternate",
        "Placeholder two-star headline, third",
    ),
    1: (
        "Placeholder one-star headline",
        "Placeholder one-star headline, alternate",
        "Placeholder one-star headline, third",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--book",
        type=Path,
        default=DEFAULT_BOOK_PATH,
        help="Path to the plain-text book source.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Page to inspect for title/context.",
    )
    parser.add_argument(
        "--rating",
        type=int,
        choices=(1, 2, 3, 4, 5),
        default=5,
        help="Star rating to include in the sample review.",
    )
    parser.add_argument(
        "--persona",
        choices=tuple(PERSONAS),
        default="beginner",
        help="Target-audience viewpoint to use for the sample review.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--post-test-review",
        action="store_true",
        help="Post the generated review to the live Firestore reviews collection as a clearly marked TEST REVIEW.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=DEFAULT_HISTORY_PATH,
        help="JSON file used to track recent sample reviews for variety across runs.",
    )
    return parser.parse_args()


def load_book_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fetch_page_html(url: str) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SampleReviewBot/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(content_type, errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def fetch_page_title(raw: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
    if not match:
        return None
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title or None


def strip_tags(raw: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_reader_reviews_context(raw: str) -> dict[str, str]:
    context: dict[str, str] = {}
    match = re.search(
        r'(<section class="reviews-section".*?</section>)',
        raw,
        flags=re.I | re.S,
    )
    if not match:
        return context

    section_html = match.group(1)
    section_text = strip_tags(section_html)
    context["section_text"] = section_text

    avg_match = re.search(
        r'id="average-rating">\s*([0-9]+(?:\.[0-9]+)?)\s*<',
        section_html,
        flags=re.I,
    )
    count_match = re.search(
        r'id="review-count">\s*([0-9]+)\s*<',
        section_html,
        flags=re.I,
    )
    if avg_match:
        context["average_rating"] = avg_match.group(1)
    if count_match:
        context["review_count"] = count_match.group(1)
    return context


def firestore_create_review(*, name: str, title: str, comment: str, rating: int) -> str:
    api_key = os.environ.get("FIREBASE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set FIREBASE_API_KEY before posting a test review.")
    endpoint = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIRESTORE_COLLECTION}"
        f"?key={api_key}"
    )
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "fields": {
            "bookSlug": {"stringValue": BOOK_SLUG},
            "name": {"stringValue": name},
            "title": {"stringValue": title},
            "comment": {"stringValue": comment},
            "rating": {"integerValue": str(rating)},
            "createdAt": {"timestampValue": created_at},
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; SampleReviewBot/1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("name", ""))


def load_review_history(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_review_history(path: Path, entries: list[dict[str, object]], *, limit: int = 200) -> None:
    path.write_text(json.dumps(entries[-limit:], indent=2) + "\n", encoding="utf-8")


def recent_history_values(
    history: list[dict[str, object]],
    key: str,
    *,
    limit: int = 12,
) -> list[str]:
    values: list[str] = []
    for item in reversed(history[-limit:]):
        value = item.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    return values


def choose_distinct_name(history: list[dict[str, object]]) -> str:
    recent_names = set(recent_history_values(history, "commenter_name", limit=40))
    candidates = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    unused = [name for name in candidates if name not in recent_names]
    pool = unused or candidates
    return random.choice(pool)


def choose_reviewer_style(history: list[dict[str, object]]) -> tuple[str, dict[str, tuple[str, ...] | str]]:
    recent_styles = recent_history_values(history, "style_key", limit=5)
    style_keys = list(REVIEWER_STYLES)
    available = [key for key in style_keys if key not in recent_styles]
    chosen_key = random.choice(available or style_keys)
    return chosen_key, REVIEWER_STYLES[chosen_key]


def choose_review_shape(history: list[dict[str, object]]) -> str:
    recent_shapes = recent_history_values(history, "shape_key", limit=5)
    available = [shape for shape in REVIEW_SHAPES if shape not in recent_shapes]
    return random.choice(available or list(REVIEW_SHAPES))


def choose_review_length(history: list[dict[str, object]]) -> str:
    recent_lengths = recent_history_values(history, "length_mode", limit=4)
    modes = ("short", "medium", "long")
    available = [mode for mode in modes if mode not in recent_lengths]
    return random.choice(available or list(modes))


def history_topic_penalties(history: list[dict[str, object]]) -> Counter[str]:
    penalties: Counter[str] = Counter()
    for index, item in enumerate(reversed(history[-10:]), start=1):
        topics = item.get("topics")
        if not isinstance(topics, list):
            continue
        for topic in topics:
            if isinstance(topic, str):
                penalties[topic] += max(1, 11 - index)
    return penalties


def summarize_recent_comments(history: list[dict[str, object]], *, limit: int = 5) -> str:
    recent_comments = recent_history_values(history, "posted_comment", limit=limit)
    if not recent_comments:
        return "None."
    return "\n".join(f"- {comment}" for comment in recent_comments)


def choose_headline(
    *,
    rating: int,
    persona_key: str,
    history: list[dict[str, object]],
) -> str:
    persona = PERSONAS[persona_key]
    templates = HEADLINE_TEMPLATES.get(rating) or HEADLINE_TEMPLATES[5]
    recent_titles = set(recent_history_values(history, "title", limit=20))
    candidates = [template.format(label=persona["label"]) for template in templates]
    available = [title for title in candidates if title not in recent_titles]
    pool = available or candidates
    return random.choice(pool)


def build_codex_review_comment_prompt(
    *,
    rating: int,
    persona_key: str,
    page_title: str | None,
    draft_review: str,
    reviewer_style_label: str,
    recent_comments_text: str,
) -> str:
    persona = PERSONAS[persona_key]
    project_reference = page_title or "this simulation question book"
    return textwrap.dedent(
        f"""\
        Write a short reader-style review comment for {project_reference}.

        Requirements:
        - First person.
        - 2 or 3 sentences.
        - Roughly 45 to 90 words total.
        - Sound natural and specific, not salesy.
        - Match a {rating}/5 tone.
        - Perspective: {persona['label']}.
        - Voice: {reviewer_style_label}.
        - Mention 1 or 2 concrete strengths from the draft.
        - Prefer concrete details from the "Notes pulled from the manuscript" section when choosing what to mention.
        - Make this clearly distinct from the recent review comments listed below.
        - Do not use formulaic openings like "I picked this up as..." or "I came to this as...".
        - Avoid the exact structure "identity sentence -> two positives -> one mild caveat".
        - Vary sentence rhythm and keep it sounding like one person talking, not a polished blurb.
        - No intro label, no quotation marks, no bullet points.
        - Return only the final review comment text.

        Recent review comments to avoid echoing:
        {recent_comments_text}

        Source draft:
        {draft_review}
        """
    ).strip()


def generate_short_review_with_codex(
    *,
    rating: int,
    persona_key: str,
    page_title: str | None,
    draft_review: str,
    reviewer_style_label: str,
    recent_comments_text: str,
) -> str:
    codex_bin = resolve_codex_bin()
    prompt = build_codex_review_comment_prompt(
        rating=rating,
        persona_key=persona_key,
        page_title=page_title,
        draft_review=draft_review,
        reviewer_style_label=reviewer_style_label,
        recent_comments_text=recent_comments_text,
    )

    with tempfile.TemporaryDirectory(prefix="sample-review-codex-") as tmp_dir:
        last_message_path = Path(tmp_dir) / "last_message.txt"
        command = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--output-last-message",
            str(last_message_path),
            "-",
        ]
        proc = subprocess.run(
            command,
            cwd=ROOT,
            input=prompt,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.strip() or proc.stdout.strip() or "unknown Codex error"
            raise SystemExit(f"Codex failed to generate post-test review text: {stderr}")

        comment = last_message_path.read_text(encoding="utf-8").strip()
        if not comment:
            raise SystemExit("Codex returned an empty post-test review comment.")
        return comment


def sentence_candidates(text: str) -> list[str]:
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    candidates: list[str] = []
    for sentence in raw_sentences:
        clean = re.sub(r"\s+", " ", sentence).strip()
        if len(clean) < 60 or len(clean) > 220:
            continue
        if "Chapter " in clean or "Key takeaway." in clean or "What to do tonight." in clean:
            continue
        candidates.append(clean)
    return candidates


def top_topics(
    text: str,
    *,
    history: list[dict[str, object]],
    limit: int = 3,
) -> list[str]:
    hits = Counter()
    for label, pattern in TOPIC_PATTERNS:
        hits[label] = len(pattern.findall(text))
    penalties = history_topic_penalties(history)
    scored: list[tuple[float, str]] = []
    for label, count in hits.items():
        if count <= 0:
            continue
        score = count - (penalties[label] * 0.2) + random.random()
        scored.append((score, label))
    ranked = [label for _score, label in sorted(scored, reverse=True)]
    if len(ranked) <= limit:
        return ranked
    sample_size = random.randint(1, limit)
    shortlist = ranked[: min(len(ranked), limit + 2)]
    return random.sample(shortlist, k=sample_size)


def join_phrases(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def pick_supporting_points(
    text: str,
    *,
    history: list[dict[str, object]],
) -> tuple[str, str]:
    sentences = sentence_candidates(text)
    fallback_a = "Placeholder note pulled from the manuscript about the claim."
    fallback_b = "Placeholder note pulled from the manuscript about the objections."
    recent_points = set(recent_history_values(history, "point_a", limit=12))
    recent_points.update(recent_history_values(history, "point_b", limit=12))

    bucket_a = [
        s for s in sentences
        if re.search(r"\b(begin|start|claim|argument|assumption|hypothesis)\b", s, re.I)
        and s not in recent_points
    ]
    bucket_b = [
        s for s in sentences
        if re.search(r"\b(objection|evidence|probability|caution|limit|uncertainty)\b", s, re.I)
        and s not in recent_points
    ]
    pool = [s for s in sentences if s not in recent_points] or sentences[:]
    random.shuffle(pool)

    point_a = random.choice(bucket_a) if bucket_a else (pool[0] if pool else fallback_a)

    remaining_bucket_b = [s for s in bucket_b if s != point_a]
    remaining_pool = [s for s in pool if s != point_a]
    point_b = (
        random.choice(remaining_bucket_b)
        if remaining_bucket_b
        else (remaining_pool[0] if remaining_pool else fallback_b)
    )
    return point_a, point_b


def build_review(
    *,
    book_text: str,
    rating: int,
    persona_key: str,
    page_title: str | None,
    reviews_context: dict[str, str],
    history: list[dict[str, object]],
    reviewer_style: dict[str, tuple[str, ...] | str],
    length_mode: str,
    shape_key: str,
) -> tuple[str, list[str], tuple[str, str], str]:
    persona = PERSONAS[persona_key]
    topics = top_topics(book_text, history=history)
    point_a, point_b = pick_supporting_points(book_text, history=history)
    bridge = random.choice(tuple(reviewer_style["bridge_options"]))
    reflection = random.choice(tuple(reviewer_style["reflection_options"]))
    closing = random.choice(tuple(reviewer_style["closing_options"]))
    opening = random.choice(OPENING_LINES[shape_key])
    personal_context = random.choice(PERSONAL_CONTEXT_SNIPPETS[persona_key])
    transition = random.choice(TRANSITION_LINES)
    praise = random.choice(PRAISE_LINES)
    critique = random.choice(CRITIQUE_LINES)
    soft_critique = random.choice(SOFT_CRITIQUE_LINES)
    topic_phrase = join_phrases(topics) if topics else "the practical sections"
    topic_sentence = random.choice(TOPIC_SENTENCE_TEMPLATES).format(
        bridge=bridge,
        transition=transition,
        topic_phrase=topic_phrase,
    )

    project_reference = "this simulation question project"
    if page_title:
        project_reference = page_title

    review_section_line = ""
    average_rating = reviews_context.get("average_rating")
    review_count = reviews_context.get("review_count")
    if average_rating and review_count:
        review_section_line = (
            f"The page's Reader Reviews section currently shows an average of "
            f"{average_rating}/5 from {review_count} reviews, and this draft aims to fit that tone."
        )
    elif reviews_context.get("section_text"):
        review_section_line = (
            "I also used the Reader Reviews prompt on the page as a cue for the tone of this draft."
        )

    opening_paragraphs = {
        "immediate_reaction": (
            f"{opening} {personal_context} {topic_sentence} {praise}"
        ),
        "specific_takeaway": (
            f"{opening} {topic_sentence} {personal_context} {reflection}"
        ),
        "comparison": (
            f"{opening} {praise} {topic_sentence} {reflection}"
        ),
        "personal_use_case": (
            f"{opening} {personal_context} {topic_sentence} {praise}"
        ),
        "slow_burn": (
            f"{opening} {topic_sentence} {personal_context} {reflection}"
        ),
    }
    opening_paragraph = opening_paragraphs[shape_key]

    medium_paragraphs = (
        f"Placeholder middle paragraph on {topic_phrase}. {review_section_line}".strip(),
        "Placeholder middle paragraph about the claim, the objections, and the uncertainty.",
        "Placeholder middle paragraph about patience instead of a grand conclusion.",
        f"Placeholder middle paragraph about notes concrete enough to revisit. {review_section_line}".strip(),
    )
    optional_middle = random.choice(medium_paragraphs)
    if not optional_middle:
        optional_middle = random.choice([praise, reflection])

    include_critique = rating <= 4 or random.random() < 0.45
    critique_paragraph = ""
    if include_critique:
        critique_paragraph = f"{critique} {soft_critique}"

    body_parts: list[str] = [opening_paragraph]
    if length_mode in {"medium", "long"}:
        body_parts.append(optional_middle)
    if length_mode == "long":
        remembered_note = point_a if random.random() < 0.5 else point_b
        body_parts.append(
            f"One note I actually remembered afterward was this: {remembered_note} {closing}"
        )
    else:
        body_parts.append(closing)
    if critique_paragraph and (length_mode == "long" or random.random() < 0.7):
        body_parts.append(critique_paragraph)
    elif critique_paragraph and length_mode == "short":
        body_parts[-1] = f"{body_parts[-1]} {critique_paragraph}"

    review_body = "\n\n".join(part.strip() for part in body_parts if part.strip())

    review = f"""\
Sample review only.
This is a fictional example written from the perspective of a {persona['label']}. Do not present it as a real customer testimonial.

Rating: {rating}/5
Context page: {project_reference}

Review:
{review_body}

Notes pulled from the manuscript:
- {point_a}
- {point_b}
"""
    return textwrap.dedent(review).strip() + "\n", topics, (point_a, point_b), shape_key


def main() -> int:
    args = parse_args()
    book_text = load_book_text(args.book)
    history_path = args.history.resolve()
    history = load_review_history(history_path)
    page_html = fetch_page_html(args.url)
    page_title = fetch_page_title(page_html) if page_html else None
    reviews_context = extract_reader_reviews_context(page_html) if page_html else {}
    style_key, reviewer_style = choose_reviewer_style(history)
    length_mode = choose_review_length(history)
    shape_key = choose_review_shape(history)
    review, topics, (point_a, point_b), shape_key = build_review(
        book_text=book_text,
        rating=args.rating,
        persona_key=args.persona,
        page_title=page_title,
        reviews_context=reviews_context,
        history=history,
        reviewer_style=reviewer_style,
        length_mode=length_mode,
        shape_key=shape_key,
    )

    title = choose_headline(
        rating=args.rating,
        persona_key=args.persona,
        history=history,
    )
    commenter_name = choose_distinct_name(history)
    posted_comment = ""

    if args.output:
        args.output.write_text(review, encoding="utf-8")
        print(f"Wrote sample review to {args.output}")
    elif not args.post_test_review:
        print(review)

    if args.post_test_review:
        posted_comment = generate_short_review_with_codex(
            rating=args.rating,
            persona_key=args.persona,
            page_title=page_title,
            draft_review=review,
            reviewer_style_label=str(reviewer_style["label"]),
            recent_comments_text=summarize_recent_comments(history),
        )
        document_name = firestore_create_review(
            name=commenter_name,
            title=title,
            comment=posted_comment,
            rating=args.rating,
        )
        print(f"Posted test review to Firestore: {document_name}")
        print(f"Headline: {title}")
        print(f"Name: {commenter_name}")

    history.append(
        {
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "commenter_name": commenter_name,
            "persona_key": args.persona,
            "style_key": style_key,
            "shape_key": shape_key,
            "topics": topics,
            "point_a": point_a,
            "point_b": point_b,
            "title": title,
            "rating": args.rating,
            "length_mode": length_mode,
            "draft_review": review,
            "posted_comment": posted_comment,
        }
    )
    save_review_history(history_path, history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
