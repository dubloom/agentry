import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from glyph import AgentQueryCompleted
import glyph.cli


@pytest.mark.asyncio
async def test_run_cli_executes_markdown_workflow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called_with: list[Path] = []

    async def fake_run_markdown_workflow(path: Path, **kwargs: object) -> dict[str, str]:
        called_with.append((path, kwargs))
        return {"file_path": "postcard.txt"}

    monkeypatch.setattr(glyph.cli, "run_markdown_workflow", fake_run_markdown_workflow)

    exit_code = await glyph.cli.run_cli(["workflow.md"])

    assert exit_code == 0
    assert called_with == [(Path("workflow.md"), {"initial_input": None})]
    assert capsys.readouterr().out.strip() == json.dumps({"file_path": "postcard.txt"})


@pytest.mark.asyncio
async def test_run_cli_passes_initial_input_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_markdown_workflow(path: Path, **kwargs: object) -> str:
        captured["path"] = path
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(glyph.cli, "run_markdown_workflow", fake_run_markdown_workflow)

    exit_code = await glyph.cli.run_cli(["workflow.md", "-i", '{"query": "x"}'])

    assert exit_code == 0
    assert captured == {"path": Path("workflow.md"), "initial_input": {"query": "x"}}
    assert capsys.readouterr().out.strip() == "ok"


@pytest.mark.asyncio
async def test_run_cli_rejects_invalid_initial_input_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def should_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("run_markdown_workflow should not run with invalid JSON")

    monkeypatch.setattr(glyph.cli, "run_markdown_workflow", should_not_run)

    with pytest.raises(SystemExit):
        await glyph.cli.run_cli(["workflow.md", "--initial-input", "not-json"])

    err = capsys.readouterr().err
    assert "invalid JSON" in err


def test_cli_main_runs_real_markdown_bash_workflow(tmp_path: Path) -> None:
    script_path = tmp_path / "hello.sh"
    script_path.write_text(
        """#!/usr/bin/env bash
printf 'From script file (execute.file): %s' "$GLYPH_WORKFLOW_DIR"
""",
        encoding="utf-8",
    )
    workflow_path = tmp_path / "workflow.md"
    workflow_path.write_text(
        """---
name: bashThenReturn
---

## Step: scriptFromFile

execute:
  file: hello.sh

returns:
  stdout: str
  stderr: str
  exit_code: int
""",
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = (
        src_path if not existing_pythonpath else os.pathsep.join((src_path, existing_pythonpath))
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from glyph.cli import main; raise SystemExit(main())",
            str(workflow_path),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "stdout": f"From script file (execute.file): {tmp_path}",
        "stderr": "",
        "exit_code": 0,
    }
    assert completed.stderr == ""


def test_render_result_handles_scalars_and_none() -> None:
    assert glyph.cli._render_result("hello") == "hello"
    assert glyph.cli._render_result(42) == "42"
    assert glyph.cli._render_result(None) is None


def test_render_result_returns_message_for_agent_query_completed() -> None:
    completed = AgentQueryCompleted(message="done", usage={"input_tokens": 1})
    assert glyph.cli._render_result(completed) == "done"


def test_render_result_agent_query_completed_without_message_is_none() -> None:
    assert glyph.cli._render_result(AgentQueryCompleted(message=None)) is None
