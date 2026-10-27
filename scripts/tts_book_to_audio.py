#!/usr/bin/env python3
"""
Synthesize ``book_tts.txt`` (or another text file) to audio using macOS's
built-in ``say`` tool — the same Speech Synthesis engine used for Spoken Content
/ Accessibility speech.

By default, writes one audio file per book section into ``book_tts_audio/``
(split on headings like ``Chapter. …``, ``Copyright``, ``Dedication``, etc.).
Each section file begins with a spoken announcement (e.g. ``Chapter 3. …``).
Use ``--single`` for one combined file (no per-section announcements).

With ``--progress``, the script tracks the growing output file and prints an
estimate of **wall-clock time remaining** (and percent toward that estimate),
instead of using ``say``'s built-in meter (which reflects internal buffering,
not time-to-done).

**Siri / “Voice N” names:** Names shown in System Settings are often **not**
the same strings ``say -v`` accepts. Unknown names make ``say`` **silently**
use the default voice. Use ``--list-voices`` for valid names, or set your Siri
voice as **System voice** under Accessibility → Spoken Content (macOS Ventura+)
and run **without** ``--voice`` so ``say`` uses that default.

Usage (from project root):
  python3 scripts/tts_book_to_audio.py
  python3 scripts/tts_book_to_audio.py --progress
  python3 scripts/tts_book_to_audio.py --single -o book_tts.aiff --progress
  python3 scripts/tts_book_to_audio.py --section 3
  python3 scripts/tts_book_to_audio.py --section "Build Dream Recall"
  python3 scripts/tts_book_to_audio.py -o my_audio/ --voice Samantha --rate 180
  python3 scripts/tts_book_to_audio.py --list-voices
"""
from __future__ import annotations

import argparse
import difflib
import math
import re
import platform
import shlex
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "book_tts.txt"
DEFAULT_OUTPUT_DIR = ROOT / "book_tts_audio"
DEFAULT_SINGLE_OUTPUT = ROOT / "book_tts.aiff"
DEFAULT_SECTION_EXT = ".aiff"
AUDIO_EXTENSIONS = frozenset({".aiff", ".caf", ".m4a", ".wav"})

# Empirical scale for ``say`` AIFC @ 22050 Hz mono: output file bytes ≈ this × speech seconds.
_BYTES_PER_SPEECH_SECOND: float = 22_000.0
_HEADER_BYTES_EST: int = 12_000

# First column of `say -v '?'` lines: name, then locale, then `#` sample.
_SAY_VOICE_LINE = re.compile(r"^(.+?)\s+([a-z]{2}_[A-Za-z0-9]+)\s+#")
_SECTION_HEADING = re.compile(
    r"^(?:Chapter(?: \d+)?\. .+|Copyright|Dedication|Glossary|References)\s*$",
    re.MULTILINE,
)
_CHAPTER_PREFIX_RE = re.compile(r"^Chapter(?: (\d+))?\. (.+)$")
_CHAPTER_STEM = re.compile(r"^(\d+)-")
_STRAY_BOX_ARTIFACT_RE = re.compile(
    r"(?im)^[ \t]*[a-z]+box[a-z]*(?:[a-z]+box[a-z]*)?\}?[ \t]*$"
)


def slugify(title: str, max_len: int = 48) -> str:
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("ascii")
    title = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return title[:max_len].rstrip("-")


def _sanitize_tts_text(text: str) -> str:
    """Strip leftover LaTeX environment-name artifacts from exported TTS text."""
    text = _STRAY_BOX_ARTIFACT_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_tts_sections(text: str) -> list[tuple[str, str, str]]:
    """Return ``(filename_stem, heading, body)`` for each section."""
    matches = list(_SECTION_HEADING.finditer(text))
    if not matches:
        return []

    preamble = text[: matches[0].start()].strip()
    sections: list[tuple[str, str, str]] = []
    chapter_n = 0

    for i, m in enumerate(matches):
        heading = m.group().strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if i == 0 and preamble:
            body = f"{preamble}\n\n{body}" if body else preamble

        chapter_match = _CHAPTER_PREFIX_RE.match(heading)
        if chapter_match:
            chapter_n += 1
            title = chapter_match.group(2)
            stem = f"{chapter_n:02d}-{slugify(title)}"
        else:
            stem = slugify(heading)

        sections.append((stem, heading, body))

    return sections


def _chapter_number_from_stem(stem: str) -> int | None:
    m = _CHAPTER_STEM.match(stem)
    return int(m.group(1)) if m else None


def _section_spoken_intro(heading: str, *, chapter_number: int | None = None) -> str:
    """Line spoken at the start of a section file (not repeated in ``book_tts.txt`` body)."""
    chapter_match = _CHAPTER_PREFIX_RE.match(heading)
    if chapter_match:
        title = chapter_match.group(2).strip()
        existing_number = chapter_match.group(1)
        if chapter_number is not None:
            return f"Chapter {chapter_number}. {title}"
        if existing_number is not None:
            return f"Chapter {existing_number}. {title}"
        return f"Chapter. {title}"
    return heading


def _section_speak_text(stem: str, heading: str, body: str) -> str:
    intro = _section_spoken_intro(heading, chapter_number=_chapter_number_from_stem(stem))
    body = body.strip()
    return f"{intro}\n\n{body}" if body else intro


def _resolve_section_specs(
    sections: list[tuple[str, str, str]],
    specs: list[str],
) -> list[tuple[str, str, str]] | None:
    """Pick sections by 1-based index, filename stem, or heading substring."""
    chosen: list[tuple[str, str, str]] = []
    seen_stems: set[str] = set()

    for spec in specs:
        spec = spec.strip()
        if not spec:
            print("Empty --section value.", file=sys.stderr)
            return None

        match: tuple[str, str, str] | None = None
        if spec.isdigit():
            idx = int(spec)
            if 1 <= idx <= len(sections):
                match = sections[idx - 1]
            else:
                print(
                    f"Section index {idx} out of range (1–{len(sections)}).",
                    file=sys.stderr,
                )
                return None
        else:
            stem_key = spec.lower().removesuffix(DEFAULT_SECTION_EXT)
            fold = spec.casefold()
            for stem, heading, _body in sections:
                if stem.casefold() == stem_key or stem_key in stem.casefold():
                    match = (stem, heading, _body)
                    break
                if fold in heading.casefold():
                    match = (stem, heading, _body)
                    break

        if match is None:
            print(f"No section matched --section {spec!r}.", file=sys.stderr)
            print("Available sections:", file=sys.stderr)
            for i, (stem, heading, _body) in enumerate(sections, start=1):
                print(f"  {i}: {heading}  ({stem})", file=sys.stderr)
            return None

        stem, _heading, _body = match
        if stem not in seen_stems:
            seen_stems.add(stem)
            chosen.append(match)

    return chosen


def _is_single_file_mode(*, single_flag: bool, output: Path) -> bool:
    if single_flag:
        return True
    return output.suffix.lower() in AUDIO_EXTENSIONS


def _say_voice_names() -> list[str]:
    proc = subprocess.run(
        ["say", "-v", "?"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("`say -v '?'` failed; cannot list voices.")
    names: list[str] = []
    for line in proc.stdout.splitlines():
        m = _SAY_VOICE_LINE.match(line)
        if m:
            names.append(m.group(1).strip())
    return names


def _resolve_say_voice(user: str) -> tuple[str | None, list[str]]:
    """Return ``(canonical_name, close_matches)``; canonical is None if unknown."""
    names = _say_voice_names()
    name_set = set(names)
    if user in name_set:
        return user, []
    fold = {n.casefold(): n for n in names}
    if user.casefold() in fold:
        return fold[user.casefold()], []
    close = difflib.get_close_matches(user, names, n=6, cutoff=0.45)
    return None, close


def _build_say_argv(
    *,
    input_path: Path,
    output_path: Path,
    voice: str | None,
    rate: int | None,
) -> list[str]:
    argv: list[str] = ["say"]
    if voice is not None:
        argv.extend(["-v", voice])
    if rate is not None:
        argv.extend(["-r", str(rate)])
    argv.extend(["-f", str(input_path), "-o", str(output_path)])
    return argv


def _word_count(text: str) -> int:
    return len(text.split())


def _speech_seconds(word_count: int, wpm: float) -> float:
    if wpm <= 0:
        wpm = 175.0
    return (word_count * 60.0) / wpm


def _human_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n / (1024 * 1024):.1f} MiB"


def _fmt_duration(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        return "…"
    if seconds >= 3600:
        h, r = divmod(int(seconds + 0.5), 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(int(seconds + 0.5), 60)
    return f"{m}:{s:02d}" if m else f"{s}s"


def _monitor_synthesis_progress(
    *,
    output_path: Path,
    expected_bytes: float,
    speech_sec: float,
    proc: subprocess.Popen,
    start_t: float,
    poll_interval: float = 0.35,
) -> None:
    """Print \\r-updated line: wall ETA + percent done from elapsed vs (elapsed + ETA)."""
    last_size = 0
    last_t = start_t
    smooth_bps: float | None = None
    alpha = 0.35
    width = 0
    wall_guess = max(25.0, speech_sec / 110.0)
    bps_boot = expected_bytes / wall_guess
    while proc.poll() is None:
        now = time.perf_counter()
        elapsed = now - start_t
        try:
            cur = output_path.stat().st_size if output_path.exists() else 0
        except OSError:
            cur = 0
        dt = now - last_t
        if dt >= poll_interval:
            if dt > 0 and cur >= last_size:
                inst = (cur - last_size) / dt
                if inst > 0:
                    smooth_bps = inst if smooth_bps is None else alpha * inst + (1 - alpha) * smooth_bps
            last_size = cur
            last_t = now

        remain_b = max(expected_bytes - cur, 0.0)
        bps = smooth_bps if (smooth_bps and smooth_bps > 200) else bps_boot
        eta = remain_b / max(bps, 200.0)
        eta = min(eta, 48 * 3600.0)  # cap absurd ETAs for display / math

        # Percent "how far through until finished" from wall-clock model.
        if elapsed + eta > 1e-3:
            pct_done = min(99.9, 100.0 * elapsed / (elapsed + eta))
        else:
            pct_done = 0.0

        line = f"~{_fmt_duration(eta)} left  ({pct_done:4.1f}% until finished)"
        width = max(width, len(line))
        sys.stdout.write("\r" + line.ljust(width))
        sys.stdout.flush()
        time.sleep(poll_interval)

    try:
        final = output_path.stat().st_size if output_path.exists() else 0
    except OSError:
        final = 0
    line = f"~0:00 left  (100.0% until finished)  [{_human_bytes(final)} written]"
    width = max(width, len(line))
    sys.stdout.write("\r" + line.ljust(width) + "\n")
    sys.stdout.flush()


def _synthesize_file(
    *,
    input_path: Path,
    output_path: Path,
    voice: str | None,
    rate: int | None,
    progress: bool,
    bytes_per_speech_second: float,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    argv = _build_say_argv(
        input_path=input_path,
        output_path=output_path,
        voice=voice,
        rate=rate,
    )
    print("Running:", " ".join(shlex.quote(a) for a in argv), flush=True)

    if progress:
        text = input_path.read_text(encoding="utf-8", errors="replace")
        words = _word_count(text)
        wpm = float(rate) if rate is not None else 175.0
        speech_sec = _speech_seconds(words, wpm)
        expected_bytes = float(bytes_per_speech_second) * speech_sec + float(_HEADER_BYTES_EST)
        print(
            f"(ETA model: ~{words} words, ~{_fmt_duration(speech_sec)} speech @ {wpm:.0f} wpm → "
            f"~{_human_bytes(int(expected_bytes))} expected on disk)",
            flush=True,
        )
        start_t = time.perf_counter()
        proc = subprocess.Popen(argv)
        try:
            _monitor_synthesis_progress(
                output_path=output_path,
                expected_bytes=expected_bytes,
                speech_sec=speech_sec,
                proc=proc,
                start_t=start_t,
            )
        finally:
            if proc.poll() is None:
                proc.kill()
        proc.wait()
        if proc.returncode != 0:
            print(f"`say` exited with status {proc.returncode}.", file=sys.stderr)
            return proc.returncode
    else:
        proc = subprocess.run(argv, check=False)
        if proc.returncode != 0:
            print(f"`say` exited with status {proc.returncode}.", file=sys.stderr)
            return proc.returncode

    print(f"Wrote: {output_path}", flush=True)
    return 0


def _synthesize_sections(
    *,
    text: str,
    output_dir: Path,
    voice: str | None,
    rate: int | None,
    progress: bool,
    bytes_per_speech_second: float,
    sections: list[tuple[str, str, str]] | None = None,
    section_ext: str = DEFAULT_SECTION_EXT,
) -> int:
    if sections is None:
        sections = _split_tts_sections(text)
    if not sections:
        print(
            "No section headings found in input. Expected lines like "
            "'Chapter. …', 'Copyright', 'Dedication', 'Glossary', or 'References'.",
            file=sys.stderr,
        )
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    failed = False

    try:
        total = len(sections)
        for idx, (stem, heading, body) in enumerate(sections, start=1):
            print(f"\nSection {idx}/{total}: {heading}", flush=True)
            txt_path = tmp_dir / f"{stem}.txt"
            audio_path = output_dir / f"{stem}{section_ext}"
            txt_path.write_text(
                _section_speak_text(stem, heading, body) + "\n",
                encoding="utf-8",
            )
            rc = _synthesize_file(
                input_path=txt_path,
                output_path=audio_path,
                voice=voice,
                rate=rate,
                progress=progress,
                bytes_per_speech_second=bytes_per_speech_second,
            )
            if rc != 0:
                failed = True
                return rc
            written.append(audio_path)
    finally:
        if failed:
            print(f"Keeping temp text files in {tmp_dir} for debugging.", flush=True)
        elif tmp_dir.exists():
            shutil.rmtree(tmp_dir)

    print(f"\nWrote {len(written)} section files to {output_dir}/", flush=True)
    for path in written:
        print(f"  {path.name}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a text file to audio with macOS `say` (Spoken Content engine).",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"UTF-8 text file to speak (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for section audio (default: {DEFAULT_OUTPUT_DIR}), "
        "or a single audio file path when using --single or an audio extension.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Write one combined audio file instead of a folder of section files.",
    )
    parser.add_argument(
        "--section",
        action="append",
        metavar="SPEC",
        default=None,
        help="Synthesize only matching section(s): 1-based index (e.g. 3), filename stem "
        "(e.g. 02-assumptions), or substring of the heading. Repeat for multiple.",
    )
    parser.add_argument(
        "-v",
        "--voice",
        default=None,
        help="Voice name as shown by --list-voices / `say -v '?'` (first column). "
        "Quote names with spaces or parentheses in zsh/bash. "
        "Omit to use the system default voice (set under Accessibility → Spoken Content; "
        "needed for many Siri voices).",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Print voice names understood by `say -v` (then exit).",
    )
    parser.add_argument(
        "--skip-voice-check",
        action="store_true",
        help="Pass --voice through to `say` without validating (not recommended).",
    )
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=None,
        metavar="WPM",
        help="Words per minute (speech rate). Omit for system default.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show wall-clock ETA and percent done (from output file growth), not `say --progress`.",
    )
    parser.add_argument(
        "--bytes-per-speech-second",
        type=float,
        default=_BYTES_PER_SPEECH_SECOND,
        metavar="BYTES",
        help="Tune expected output size: expected_bytes ≈ header + speech_seconds × this "
        f"(default: {_BYTES_PER_SPEECH_SECOND:.0f}). Raise if the bar stalls below ~100%%.",
    )
    args = parser.parse_args()

    if platform.system() != "Darwin":
        print("This script requires macOS (Darwin).", file=sys.stderr)
        return 1
    say = shutil.which("say")
    if say is None:
        print("Could not find `say` on PATH.", file=sys.stderr)
        return 1

    if args.list_voices:
        try:
            for n in sorted(_say_voice_names(), key=str.casefold):
                print(n)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1
        return 0

    input_path: Path = args.input.expanduser().resolve()
    single_mode = _is_single_file_mode(single_flag=args.single, output=args.output)
    if single_mode and args.single and args.output == DEFAULT_OUTPUT_DIR:
        output_path = DEFAULT_SINGLE_OUTPUT.expanduser().resolve()
    elif single_mode:
        output_path = args.output.expanduser().resolve()
    else:
        output_path = args.output.expanduser().resolve()

    if not input_path.is_file():
        print(f"Input not found or not a file: {input_path}", file=sys.stderr)
        return 1

    voice_arg: str | None = args.voice
    if voice_arg is not None and not args.skip_voice_check:
        try:
            resolved, hints = _resolve_say_voice(voice_arg)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1
        if resolved is None:
            print(
                f"Unknown voice for `say -v`: {voice_arg!r}\n"
                "macOS does not error on invalid names; it falls back to the default voice.\n"
                "Run `python3 scripts/tts_book_to_audio.py --list-voices` and pick an exact name.\n"
                "For Siri-style voices from System Settings, they are often not exposed here; set that "
                "voice as the system “spoken content” voice and omit `--voice`.\n",
                file=sys.stderr,
            )
            if hints:
                print("Close matches:", file=sys.stderr)
                for h in hints:
                    print(f"  {h}", file=sys.stderr)
            return 1
        if resolved != voice_arg:
            print(f"(Using voice {resolved!r} from --voice {voice_arg!r})", flush=True)
        voice_arg = resolved

    text = _sanitize_tts_text(input_path.read_text(encoding="utf-8", errors="replace"))

    if single_mode:
        if args.section:
            print("--section cannot be used with --single or an audio file -o path.", file=sys.stderr)
            return 1
        tmp_input = output_path.parent / f".{output_path.stem}.tts-input.txt"
        tmp_input.parent.mkdir(parents=True, exist_ok=True)
        tmp_input.write_text(text + "\n", encoding="utf-8")
        try:
            return _synthesize_file(
                input_path=tmp_input,
                output_path=output_path,
                voice=voice_arg,
                rate=args.rate,
                progress=args.progress,
                bytes_per_speech_second=args.bytes_per_speech_second,
            )
        finally:
            if tmp_input.exists():
                tmp_input.unlink()

    all_sections = _split_tts_sections(text)
    if args.section:
        selected = _resolve_section_specs(all_sections, args.section)
        if selected is None:
            return 1
        sections = selected
    else:
        sections = all_sections

    return _synthesize_sections(
        text=text,
        output_dir=output_path,
        voice=voice_arg,
        rate=args.rate,
        progress=args.progress,
        bytes_per_speech_second=args.bytes_per_speech_second,
        sections=sections,
    )


if __name__ == "__main__":
    raise SystemExit(main())
