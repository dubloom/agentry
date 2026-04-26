"""Command-line entry points for Glyph."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from typing import Sequence

from glyph.messages import AgentQueryCompleted
from glyph.workflow import run_markdown_workflow


def build_parser() -> argparse.ArgumentParser:
    """Build the ``glyph`` CLI parser."""
    parser = argparse.ArgumentParser(description="Run a Glyph Markdown workflow.")
    parser.add_argument("workflow", type=Path, help="Path to the workflow Markdown file.")
    parser.add_argument(
        "--initial-input",
        "-i",
        metavar="JSON",
        help="JSON for the workflow's initial_input (object, array, or scalar).",
        default=None,
    )
    return parser


def _render_result(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, AgentQueryCompleted):
        return result.message
    if isinstance(result, (str, int, float, bool)):
        return str(result)
    return json.dumps(result)


async def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with ``argv`` and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    initial_input: Any = None
    if args.initial_input is not None:
        try:
            initial_input = json.loads(args.initial_input)
        except json.JSONDecodeError as exc:
            parser.error(f"invalid JSON for --initial-input: {exc}")

    result = await run_markdown_workflow(args.workflow, initial_input=initial_input)
    rendered = _render_result(result)
    if rendered is not None:
        print(rendered)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous console entry point."""
    return asyncio.run(run_cli(argv))
