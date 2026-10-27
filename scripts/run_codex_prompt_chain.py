#!/usr/bin/env python3
"""
Run a sequence of Codex CLI prompts, waiting for each step to finish before
starting the next one.

The chain is defined in a JSON file. Each step can provide either:
  - "prompt": inline text
  - "prompt_file": path to a UTF-8 text file

Template tokens available inside prompts:
  {{previous_output}}   Last message from the immediately previous step
  {{output:step_name}}  Last message from a named earlier step
  {{thread_id}}         Current Codex thread id

Example:
  python3 scripts/run_codex_prompt_chain.py scripts/prompt_chain.example.json
  python3 scripts/run_codex_prompt_chain.py scripts/prompt_chain.example.json --dry-run

Example chain file:
{
  "continue_session": true,
  "full_auto": true,
  "steps": [
    {
      "name": "draft",
      "prompt": "Write a first-pass prompt for revising chapter 1."
    },
    {
      "name": "refine",
      "prompt": "Improve the prompt below and make it more specific.\\n\\n{{previous_output}}"
    }
  ]
}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")


def resolve_codex_bin() -> str:
    env_value = os.environ.get("CODEX_BIN")
    if env_value:
        candidate = Path(env_value).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(env_value)
        if found:
            return found

    found = shutil.which("codex")
    if found:
        return found

    cursor_roots = sorted(
        Path.home().glob(".cursor/extensions/openai.chatgpt-*/bin/macos-aarch64/codex")
    )
    if cursor_roots:
        return str(cursor_roots[-1].resolve())

    raise SystemExit(
        "Could not find `codex` in PATH.\n"
        "Set CODEX_BIN to the Codex CLI path, or add the Codex binary to PATH."
    )


@dataclass
class StepResult:
    name: str
    exit_code: int
    thread_id: str | None
    last_message: str
    prompt_path: Path
    stdout_path: Path
    stderr_path: Path
    last_message_path: Path
    command: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a JSON-defined sequence of Codex prompts. Each prompt waits for the "
            "previous command to finish before the next prompt starts."
        )
    )
    parser.add_argument(
        "chain",
        type=Path,
        help="Path to the JSON chain definition.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help=(
            "Directory where prompts, stdout/stderr logs, and final messages will be "
            "stored. Defaults to codex_runs/<timestamp>."
        ),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT,
        help="Working directory for Codex runs. Defaults to the project root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render prompts and write artifacts without executing Codex.",
    )
    return parser.parse_args()


def load_chain(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Chain file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("Chain file must be a JSON object.")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise SystemExit('Chain file must contain a non-empty "steps" array.')

    return data


def resolve_output_dir(
    cli_output_dir: Path | None,
    chain: dict[str, Any],
    *,
    chain_dir: Path,
) -> Path:
    if cli_output_dir is not None:
        return cli_output_dir.resolve()

    configured = chain.get("output_dir")
    if configured:
        return (chain_dir / str(configured)).resolve()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (ROOT / "codex_runs" / stamp).resolve()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-").lower()
    return slug or "step"


def step_name(index: int, raw: dict[str, Any]) -> str:
    value = raw.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"step_{index:02d}"


def load_prompt(step: dict[str, Any], *, chain_dir: Path) -> str:
    prompt = step.get("prompt")
    prompt_file = step.get("prompt_file")

    if prompt is not None and prompt_file is not None:
        raise SystemExit('Each step may define either "prompt" or "prompt_file", not both.')

    if isinstance(prompt, str):
        return prompt

    if isinstance(prompt_file, str) and prompt_file.strip():
        prompt_path = (chain_dir / prompt_file).resolve()
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SystemExit(f"Prompt file not found: {prompt_path}") from exc

    raise SystemExit('Each step must define either "prompt" or "prompt_file".')


def render_prompt(
    text: str,
    *,
    previous_output: str | None,
    outputs_by_name: dict[str, str],
    thread_id: str | None,
) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if token == "previous_output":
            if previous_output is None:
                raise SystemExit(
                    'Template token "{{previous_output}}" was used before any step completed.'
                )
            return previous_output

        if token == "thread_id":
            if thread_id is None:
                raise SystemExit(
                    'Template token "{{thread_id}}" was used before a Codex thread existed.'
                )
            return thread_id

        if token.startswith("output:"):
            name = token.split(":", 1)[1].strip()
            if name not in outputs_by_name:
                available = ", ".join(sorted(outputs_by_name)) or "none"
                raise SystemExit(
                    f'Unknown template token "{{{{{token}}}}}". Available named outputs: {available}.'
                )
            return outputs_by_name[name]

        raise SystemExit(
            f'Unsupported template token "{{{{{token}}}}}". '
            'Use {{previous_output}}, {{thread_id}}, or {{output:step_name}}.'
        )

    return TOKEN_RE.sub(replace, text)


def parse_jsonl_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def find_thread_id(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str) and thread_id:
                return thread_id
    return None


def common_codex_args(chain: dict[str, Any]) -> list[str]:
    args: list[str] = []

    model = chain.get("model")
    if model is not None:
        args.extend(["--model", str(model)])

    full_auto = bool(chain.get("full_auto", False))
    dangerous = bool(chain.get("dangerously_bypass_approvals_and_sandbox", False))
    if full_auto and dangerous:
        raise SystemExit("Use only one of full_auto or dangerously_bypass_approvals_and_sandbox.")
    if full_auto:
        # Codex CLI 0.154 dropped --full-auto. --approve-for-me is the
        # non-interactive replacement and already uses the workspace-write sandbox.
        args.append("--approve-for-me")
    if dangerous:
        args.append("--dangerously-bypass-approvals-and-sandbox")

    if bool(chain.get("skip_git_repo_check", False)):
        args.append("--skip-git-repo-check")

    if bool(chain.get("ephemeral", False)):
        args.append("--ephemeral")

    config_overrides = chain.get("config_overrides", [])
    if config_overrides is None:
        config_overrides = []
    if not isinstance(config_overrides, list):
        raise SystemExit('"config_overrides" must be an array of strings.')
    for item in config_overrides:
        if not isinstance(item, str):
            raise SystemExit('"config_overrides" entries must be strings.')
        args.extend(["-c", item])

    return args


def run_step(
    *,
    codex_bin: str,
    workspace: Path,
    output_dir: Path,
    index: int,
    name: str,
    prompt: str,
    thread_id: str | None,
    continue_session: bool,
    common_args: list[str],
    dry_run: bool,
) -> StepResult:
    step_dir = output_dir / f"{index:02d}-{slugify(name)}"
    step_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = step_dir / "prompt.txt"
    stdout_path = step_dir / "stdout.jsonl"
    stderr_path = step_dir / "stderr.log"
    last_message_path = step_dir / "last_message.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    if continue_session and thread_id:
        # `codex exec resume` rejects --approve-for-me. The first exec already
        # set that approval mode on the thread.
        resume_args = [arg for arg in common_args if arg != "--approve-for-me"]
        command = [
            codex_bin,
            "exec",
            "resume",
            "--json",
            "--output-last-message",
            str(last_message_path),
            *resume_args,
            thread_id,
            "-",
        ]
    else:
        command = [
            codex_bin,
            "exec",
            "--json",
            "--output-last-message",
            str(last_message_path),
            *common_args,
            "-",
        ]

    if dry_run:
        simulated_thread_id = thread_id or "dry-run-thread"
        simulated_output = f"[dry-run placeholder output for {name}]"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        last_message_path.write_text(simulated_output, encoding="utf-8")
        return StepResult(
            name=name,
            exit_code=0,
            thread_id=simulated_thread_id,
            last_message=simulated_output,
            prompt_path=prompt_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            last_message_path=last_message_path,
            command=command,
        )

    proc = subprocess.run(
        command,
        cwd=workspace,
        input=prompt,
        capture_output=True,
        text=True,
    )

    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    events = parse_jsonl_events(proc.stdout)
    discovered_thread_id = find_thread_id(events) or thread_id

    last_message = ""
    if last_message_path.is_file():
        last_message = last_message_path.read_text(encoding="utf-8")

    return StepResult(
        name=name,
        exit_code=proc.returncode,
        thread_id=discovered_thread_id,
        last_message=last_message,
        prompt_path=prompt_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        last_message_path=last_message_path,
        command=command,
    )


def write_summary(output_dir: Path, results: list[StepResult]) -> Path:
    payload = {
        "steps": [
            {
                "name": result.name,
                "exit_code": result.exit_code,
                "thread_id": result.thread_id,
                "prompt_path": str(result.prompt_path),
                "stdout_path": str(result.stdout_path),
                "stderr_path": str(result.stderr_path),
                "last_message_path": str(result.last_message_path),
                "command": result.command,
            }
            for result in results
        ]
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return summary_path


def main() -> int:
    args = parse_args()
    chain = load_chain(args.chain.resolve())

    continue_session = bool(chain.get("continue_session", True))
    if continue_session and bool(chain.get("ephemeral", False)):
        raise SystemExit('Set "ephemeral" to false when "continue_session" is true.')

    workspace = args.workspace.resolve()
    chain_path = args.chain.resolve()
    chain_dir = chain_path.parent
    output_dir = resolve_output_dir(args.output_dir, chain, chain_dir=chain_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    codex_bin = resolve_codex_bin()

    common_args = common_codex_args(chain)
    previous_output: str | None = None
    outputs_by_name: dict[str, str] = {}
    results: list[StepResult] = []
    thread_id: str | None = None
    seen_names: set[str] = set()

    steps = chain["steps"]
    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            raise SystemExit("Each step must be a JSON object.")

        name = step_name(index, raw_step)
        if name in seen_names:
            raise SystemExit(f"Duplicate step name: {name}")
        seen_names.add(name)

        template = load_prompt(raw_step, chain_dir=chain_dir)
        prompt = render_prompt(
            template,
            previous_output=previous_output,
            outputs_by_name=outputs_by_name,
            thread_id=thread_id,
        )

        result = run_step(
            codex_bin=codex_bin,
            workspace=workspace,
            output_dir=output_dir,
            index=index,
            name=name,
            prompt=prompt,
            thread_id=thread_id,
            continue_session=continue_session,
            common_args=common_args,
            dry_run=args.dry_run,
        )
        results.append(result)

        if args.dry_run:
            thread_id = result.thread_id
            previous_output = result.last_message
            outputs_by_name[name] = result.last_message
            print(f"[dry-run] prepared step {index}: {name}")
            print("  prompt:", result.prompt_path)
            print("  command:", " ".join(result.command))
            print("  simulated output:", result.last_message_path)
            continue

        if result.exit_code != 0:
            write_summary(output_dir, results)
            error_note = (
                f"Codex step {index} failed: {name}\n"
                f"stdout: {result.stdout_path}\n"
                f"stderr: {result.stderr_path}\n"
                f"last message: {result.last_message_path}\n"
            )
            sys.stderr.write(error_note)
            return result.exit_code

        if continue_session and result.thread_id is None:
            write_summary(output_dir, results)
            raise SystemExit(
                f"Step {index} completed but did not emit a thread id. See {result.stdout_path}."
            )

        thread_id = result.thread_id
        previous_output = result.last_message
        outputs_by_name[name] = result.last_message

        print(f"Completed step {index}: {name}")
        print(f"  prompt: {result.prompt_path}")
        print(f"  last message: {result.last_message_path}")
        if thread_id:
            print(f"  thread: {thread_id}")

    summary_path = write_summary(output_dir, results)
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
