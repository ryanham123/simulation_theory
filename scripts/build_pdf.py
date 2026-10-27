"""
Build main.pdf from the LaTeX project in this repo.

Prefer tectonic (bundles its own TeX); fall back to pdflatex if installed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Literal

Engine = Literal["auto", "tectonic", "pdflatex"]


def build_pdf(
    project_dir: Path | None = None,
    *,
    engine: Engine = "auto",
    pdflatex_runs: int = 2,
    quiet: bool = False,
    keep_logs: bool = False,
    keep_intermediates: bool = False,
) -> Path:
    """
    Compile ``main.tex`` in ``project_dir`` and return the path to ``main.pdf``.

    Parameters
    ----------
    project_dir
        Directory containing ``main.tex``. Defaults to the parent of ``scripts/``.
    engine
        ``"tectonic"``, ``"pdflatex"``, or ``"auto"`` (try tectonic first).
    pdflatex_runs
        Number of ``pdflatex`` passes (TOC / references usually need 2).
    quiet
        If True, suppress compiler stdout/stderr unless the build fails.
    keep_logs
        When using tectonic, keep the generated log files.
    keep_intermediates
        When using tectonic, keep intermediate files such as ``.aux`` and ``.toc``.

    Raises
    ------
    FileNotFoundError
        If ``main.tex`` or the chosen engine is missing, or PDF was not written.
    RuntimeError
        If the compiler exits non-zero.
    """
    root = (project_dir or Path(__file__).resolve().parent.parent).resolve()
    main_tex = root / "main.tex"
    if not main_tex.is_file():
        raise FileNotFoundError(f"Missing main.tex: {main_tex}")

    chosen: str
    if engine == "auto":
        if shutil.which("tectonic"):
            chosen = "tectonic"
        elif shutil.which("pdflatex"):
            chosen = "pdflatex"
        else:
            raise FileNotFoundError(
                "No LaTeX engine found. Install tectonic (brew install tectonic) "
                "or a TeX distribution with pdflatex."
            )
    else:
        chosen = engine
        if not shutil.which(chosen):
            raise FileNotFoundError(f"{chosen} not found in PATH")

    kwargs: dict = {"cwd": root, "text": True}
    if quiet:
        kwargs["capture_output"] = True

    if chosen == "tectonic":
        cmd = ["tectonic"]
        if keep_logs:
            cmd.append("--keep-logs")
        if keep_intermediates:
            cmd.append("--keep-intermediates")
        cmd.append(str(main_tex))
        proc = subprocess.run(
            cmd,
            **kwargs,
        )
        if proc.returncode != 0:
            msg = getattr(proc, "stderr", None) or getattr(proc, "stdout", None) or ""
            raise RuntimeError(f"tectonic failed (exit {proc.returncode}):\n{msg}")
    else:
        for i in range(max(1, pdflatex_runs)):
            proc = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "main.tex",
                ],
                **kwargs,
            )
            if proc.returncode != 0:
                msg = getattr(proc, "stderr", None) or getattr(proc, "stdout", None) or ""
                raise RuntimeError(
                    f"pdflatex failed on pass {i + 1} (exit {proc.returncode}):\n{msg}"
                )

    pdf = root / "main.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"Expected PDF not found: {pdf}")
    return pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        type=Path,
        help="Directory containing main.tex (defaults to the repo root).",
    )
    parser.add_argument(
        "--engine",
        choices=("auto", "tectonic", "pdflatex"),
        default="auto",
        help="LaTeX engine to use.",
    )
    parser.add_argument(
        "--pdflatex-runs",
        type=int,
        default=2,
        help="Number of pdflatex passes when using the pdflatex engine.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress compiler output unless the build fails.",
    )
    parser.add_argument(
        "--keep-logs",
        action="store_true",
        help="Keep tectonic log files after the build.",
    )
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep tectonic intermediate files after the build.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    out = build_pdf(
        project_dir=args.project_dir,
        engine=args.engine,
        pdflatex_runs=args.pdflatex_runs,
        quiet=args.quiet,
        keep_logs=args.keep_logs,
        keep_intermediates=args.keep_intermediates,
    )
    print(out)
