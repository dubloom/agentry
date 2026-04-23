"""Markdown workflow loader."""

from __future__ import annotations

import importlib.util
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Literal

from glyph.messages import AgentQueryCompleted
from glyph.options import AgentOptions
from glyph.options import PermissionPolicy

from .decorators import step


_STEP_HEADING_RE = re.compile(r"^## Step:\s*(?P<step_id>.+?)\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_PROMPT_VARIABLE_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
_METADATA_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*:")

_SCALAR_TYPES: dict[str, type[Any]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
}


MarkdownStepKind = Literal["execute", "llm", "stop"]


@dataclass(frozen=True)
class MarkdownStep:
    step_id: str
    kind: MarkdownStepKind
    execute: str | None
    prompt: str | None
    model: str | None
    stop: str | None
    returns: str | dict[str, str] | None


@dataclass(frozen=True)
class MarkdownWorkflowDefinition:
    name: str
    path: Path
    entrypoint: str
    options: AgentOptions | None
    steps: tuple[MarkdownStep, ...]


def load_markdown_workflow(path: str | Path) -> type:
    """Build a ``GlyphWorkflow`` subclass from ``path``."""

    from . import GlyphWorkflow

    workflow_path = Path(path).expanduser().resolve()
    definition = parse_markdown_workflow(workflow_path)

    attrs: dict[str, Any] = {
        "__module__": GlyphWorkflow.__module__,
        "__doc__": f"Markdown workflow loaded from {workflow_path}.",
        "options": definition.options,
        "_glyph_markdown_path": str(workflow_path),
        "_glyph_markdown_entrypoint": definition.entrypoint,
    }

    for index, step_definition in enumerate(_ordered_steps(definition)):
        method_name = _step_method_name(index, step_definition.step_id)
        attrs[method_name] = _build_step_method(
            workflow_path=workflow_path,
            step_definition=step_definition,
            method_name=method_name,
        )

    workflow_name = _class_name(definition.name)
    workflow_cls = type(workflow_name, (GlyphWorkflow,), attrs)
    setattr(workflow_cls, "_glyph_markdown_definition", definition)
    return workflow_cls


async def run_markdown_workflow(
    path: str | Path,
    *,
    options: AgentOptions | None = None,
    session_id: str | None = None,
    initial_input: Any = None,
) -> Any:
    """Load and run a workflow defined in Markdown."""

    workflow_cls = load_markdown_workflow(path)
    return await workflow_cls.run(
        options=options,
        session_id=session_id,
        initial_input=initial_input,
    )


def parse_markdown_workflow(path: str | Path) -> MarkdownWorkflowDefinition:
    """Parse ``path`` into an intermediate workflow definition."""

    workflow_path = Path(path).expanduser().resolve()
    raw_text = workflow_path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw_text)
    body = _strip_comments(body)
    metadata = _parse_mapping_block(frontmatter.splitlines(), context="workflow frontmatter")
    steps = _parse_steps(body)
    if not steps:
        raise ValueError(f"{workflow_path} must declare at least one `## Step: ...` section.")

    entrypoint = steps[0].step_id

    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        name = workflow_path.stem

    options = _build_agent_options(
        metadata.get("options"),
        steps,
        workflow_path,
    )

    return MarkdownWorkflowDefinition(
        name=name.strip(),
        path=workflow_path,
        entrypoint=entrypoint,
        options=options,
        steps=tuple(steps),
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("Markdown workflow files must start with YAML frontmatter delimited by `---`.")

    end_index = text.find("\n---\n", 4)
    if end_index == -1:
        raise ValueError("Markdown workflow frontmatter must end with a closing `---` line.")

    frontmatter = text[4:end_index]
    body = text[end_index + len("\n---\n") :]
    return frontmatter, body


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _parse_steps(body: str) -> list[MarkdownStep]:
    matches = list(_STEP_HEADING_RE.finditer(body))
    steps: list[MarkdownStep] = []
    seen_ids: set[str] = set()
    for index, match in enumerate(matches):
        step_id = match.group("step_id").strip()
        if not step_id:
            raise ValueError("Workflow step headings must provide a non-empty id.")
        if step_id in seen_ids:
            raise ValueError(f"Duplicate workflow step id {step_id!r}.")
        seen_ids.add(step_id)

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section = body[start:end].strip("\n")
        steps.append(_parse_step_section(step_id, section))
    return steps


def _parse_step_section(step_id: str, section: str) -> MarkdownStep:
    metadata_lines, prompt = _split_step_metadata(section)
    metadata = _parse_mapping_block(metadata_lines, context=f"step {step_id!r}")

    execute = metadata.pop("execute", None)
    model = metadata.pop("model", None)
    returns = metadata.pop("returns", None)
    stop = metadata.pop("stop", None)
    is_streaming = metadata.pop("is_streaming", None)

    if metadata:
        unknown_keys = ", ".join(sorted(metadata))
        raise ValueError(f"Unknown metadata key(s) on step {step_id!r}: {unknown_keys}.")

    if is_streaming is not None:
        raise ValueError(f"Prompt-only step {step_id!r} must not declare `is_streaming` in v1.")

    if stop is not None:
        if execute is not None or model is not None or returns is not None or prompt:
            raise ValueError(f"Stop step {step_id!r} cannot declare `execute`, `model`, `returns`, or prompt text.")
        if not isinstance(stop, str) or not stop.strip():
            raise ValueError(f"Stop step {step_id!r} must declare a non-empty `stop:` value.")
        return MarkdownStep(
            step_id=step_id,
            kind="stop",
            execute=None,
            prompt=None,
            model=None,
            stop=stop.strip(),
            returns=None,
        )

    if execute is not None and prompt:
        raise ValueError(f"Step {step_id!r} cannot declare both `execute:` and prompt text in v1.")

    if execute is not None:
        if not isinstance(execute, str) or not execute.strip():
            raise ValueError(f"Execute step {step_id!r} must declare a non-empty `execute:` target.")
        if model is not None:
            raise ValueError(f"Execute step {step_id!r} must not declare `model:`.")
        normalized_returns = _normalize_returns(step_id=step_id, returns=returns)
        return MarkdownStep(
            step_id=step_id,
            kind="execute",
            execute=execute.strip(),
            prompt=None,
            model=None,
            stop=None,
            returns=normalized_returns,
        )

    if not prompt:
        raise ValueError(f"Step {step_id!r} must declare either `execute:`, prompt text, or `stop:`.")
    if returns is not None:
        raise ValueError(f"Prompt-only step {step_id!r} must not declare `returns`.")
    if model is not None and not isinstance(model, str):
        raise ValueError(f"Prompt-only step {step_id!r} must declare `model:` as a string when provided.")

    return MarkdownStep(
        step_id=step_id,
        kind="llm",
        execute=None,
        prompt=prompt,
        model=model.strip() if isinstance(model, str) else None,
        stop=None,
        returns=None,
    )


def _split_step_metadata(section: str) -> tuple[list[str], str]:
    lines = section.splitlines()
    metadata_lines: list[str] = []
    body_start = 0
    saw_metadata = False
    supported_metadata_keys = {"execute", "model", "returns", "stop"}

    while body_start < len(lines):
        line = lines[body_start]
        stripped = line.strip()
        if not stripped:
            if saw_metadata:
                body_start += 1
                while body_start < len(lines) and not lines[body_start].strip():
                    body_start += 1
                break
            body_start += 1
            continue
        if line.startswith((" ", "\t")):
            if not metadata_lines:
                break
            metadata_lines.append(line)
            saw_metadata = True
            body_start += 1
            continue
        if _METADATA_LINE_RE.match(line):
            key, _separator, _value = line.partition(":")
            if key.strip() not in supported_metadata_keys:
                break
            metadata_lines.append(line)
            saw_metadata = True
            body_start += 1
            continue
        break

    prompt = "\n".join(lines[body_start:]).strip()
    return metadata_lines, prompt


def _parse_mapping_block(lines: list[str], *, context: str) -> dict[str, Any]:
    cleaned_lines = [line.rstrip("\n") for line in lines if line.strip()]
    if not cleaned_lines:
        return {}
    parsed, next_index = _parse_mapping_lines(cleaned_lines, start=0, indent=0, context=context)
    if next_index != len(cleaned_lines):
        raise ValueError(f"Unexpected trailing content while parsing {context}.")
    return parsed


def _parse_mapping_lines(
    lines: list[str],
    *,
    start: int,
    indent: int,
    context: str,
) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    index = start

    while index < len(lines):
        line = lines[index]
        current_indent = _line_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"Unexpected indentation while parsing {context}: {line!r}")

        stripped = line[indent:]
        if ":" not in stripped:
            raise ValueError(f"Invalid metadata line while parsing {context}: {line!r}")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise ValueError(f"Invalid empty key while parsing {context}.")

        index += 1
        if raw_value:
            data[key] = _parse_scalar(raw_value)
            continue

        if index >= len(lines):
            data[key] = {}
            continue

        next_indent = _line_indent(lines[index])
        if next_indent <= current_indent:
            data[key] = {}
            continue

        nested, index = _parse_mapping_lines(
            lines,
            start=index,
            indent=next_indent,
            context=context,
        )
        data[key] = nested

    return data, index


def _parse_scalar(raw_value: str) -> Any:
    value = raw_value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item.strip()) for item in inner.split(",")]
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _normalize_returns(*, step_id: str, returns: Any) -> str | dict[str, str] | None:
    if returns is None:
        return None
    if isinstance(returns, str):
        _validate_type_name(returns, step_id=step_id)
        return returns
    if isinstance(returns, dict):
        normalized: dict[str, str] = {}
        for key, value in returns.items():
            if not isinstance(value, str):
                raise ValueError(f"Step {step_id!r} return field {key!r} must declare a scalar type alias.")
            _validate_type_name(value, step_id=step_id)
            normalized[key] = value
        return normalized
    raise ValueError(f"Step {step_id!r} `returns` must be a scalar alias or a mapping of field names to scalar aliases.")


def _validate_type_name(type_name: str, *, step_id: str) -> None:
    if type_name not in _SCALAR_TYPES and type_name != "any":
        supported = ", ".join(sorted([* _SCALAR_TYPES, "any"]))
        raise ValueError(f"Step {step_id!r} uses unsupported return type {type_name!r}; expected one of {supported}.")


def _build_agent_options(
    raw_options: Any,
    steps: list[MarkdownStep],
    workflow_path: Path,
) -> AgentOptions | None:
    if raw_options is not None and not isinstance(raw_options, dict):
        raise ValueError(f"{workflow_path} frontmatter `options` must be a mapping when provided.")

    payload = dict(raw_options or {})
    default_model = next(
        (step.model for step in steps if step.kind == "llm" and step.model is not None),
        None,
    )

    if "model" not in payload and default_model is not None:
        payload["model"] = default_model

    permission = payload.get("permission")
    if isinstance(permission, dict):
        payload["permission"] = PermissionPolicy(**permission)

    return AgentOptions(**payload) if payload else None


def _ordered_steps(definition: MarkdownWorkflowDefinition) -> tuple[MarkdownStep, ...]:
    return definition.steps


def _step_method_name(index: int, step_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", step_id).strip("_")
    if not normalized:
        normalized = "step"
    if normalized[0].isdigit():
        normalized = f"step_{normalized}"
    return f"_markdown_step_{index}_{normalized}"


def _class_name(name: str) -> str:
    pieces = re.split(r"[^A-Za-z0-9]+", name)
    normalized = "".join(piece[:1].upper() + piece[1:] for piece in pieces if piece)
    return normalized or "MarkdownWorkflow"


def _build_step_method(
    *,
    workflow_path: Path,
    step_definition: MarkdownStep,
    method_name: str,
):
    if step_definition.kind == "execute":
        handler = _load_execute_handler(step_definition.execute or "", workflow_path.parent)

        async def _execute_step(self, previous_result: Any = None) -> Any:
            result = await _invoke_execute_handler(handler, previous_result)
            _store_execute_result(
                self=self,
                step_definition=step_definition,
                result=result,
            )
            return result

        _execute_step.__name__ = method_name
        _execute_step.__qualname__ = method_name
        return step(_execute_step)

    if step_definition.kind == "llm":
        prompt_template = _compile_prompt_template(step_definition.prompt or "")

        async def _llm_step(self, previous_result: Any = None) -> None:
            del previous_result
            context = _markdown_context(self)
            self.prompt = self.fill_prompt(**context)
            return None

        _llm_step.__name__ = method_name
        _llm_step.__qualname__ = method_name
        return step(prompt=prompt_template, model=step_definition.model)(_llm_step)

    async def _stop_step(self, previous_result: Any = None) -> None:
        value = _resolve_stop_value(
            expression=step_definition.stop or "",
            previous_result=previous_result,
            context=_markdown_context(self),
        )
        self.stop_workflow(value)

    _stop_step.__name__ = method_name
    _stop_step.__qualname__ = method_name
    return step(_stop_step)


def _compile_prompt_template(prompt: str) -> str:
    return _PROMPT_VARIABLE_RE.sub(r"{\1}", prompt)


def _markdown_context(workflow: Any) -> dict[str, Any]:
    context = getattr(workflow, "_markdown_context", None)
    if context is None:
        context = {}
        setattr(workflow, "_markdown_context", context)
    return context


def _load_execute_handler(target: str, base_directory: Path):
    script_path_str, separator, function_name = target.partition(":")
    if separator == "":
        function_name = "main"
    elif not function_name.strip():
        raise ValueError(
            f"Invalid execute target {target!r}; expected `path/to/script.py:function_name` or `path/to/script.py`."
        )
    else:
        function_name = function_name.strip()

    script_path = Path(script_path_str)
    if not script_path.is_absolute():
        script_path = (base_directory / script_path).resolve()

    if script_path.suffix != ".py":
        raise ValueError(f"Execute target {target!r} must point to a Python file.")
    if not script_path.exists():
        raise ValueError(f"Execute target script {script_path} does not exist.")

    module_name = f"_glyph_markdown_{abs(hash((str(script_path), function_name)))}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {script_path}.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = getattr(module, function_name, None)
    if handler is None:
        raise AttributeError(f"{script_path} does not define {function_name!r}.")
    return handler


async def _invoke_execute_handler(handler: Any, previous_result: Any) -> Any:
    parameter_count = len(inspect.signature(handler).parameters)
    if parameter_count == 0:
        result = handler()
    elif parameter_count == 1:
        result = handler(previous_result)
    else:
        raise TypeError(
            f"Execute handler {handler.__name__!r} must accept zero or one argument, got {parameter_count}."
        )

    if inspect.isawaitable(result):
        return await result
    return result


def _store_execute_result(*, self: Any, step_definition: MarkdownStep, result: Any) -> None:
    returns = step_definition.returns
    if returns is None:
        return

    _validate_execute_result(
        result=result,
        returns=returns,
        step_id=step_definition.step_id,
    )

    if isinstance(returns, dict):
        context = _markdown_context(self)
        for key in returns:
            context[key] = result[key]


def _validate_execute_result(*, result: Any, returns: str | dict[str, str], step_id: str) -> None:
    if isinstance(returns, str):
        _validate_value(value=result, expected_type=returns, label=f"step {step_id!r} return value")
        return

    if not isinstance(result, dict):
        raise TypeError(f"Step {step_id!r} must return a dict matching its declared `returns` fields.")

    for key, type_name in returns.items():
        if key not in result:
            raise TypeError(f"Step {step_id!r} must return key {key!r} declared in `returns`.")
        _validate_value(value=result[key], expected_type=type_name, label=f"step {step_id!r} field {key!r}")


def _validate_value(*, value: Any, expected_type: str, label: str) -> None:
    if expected_type == "any":
        return
    expected_python_type = _SCALAR_TYPES[expected_type]
    if not isinstance(value, expected_python_type):
        raise TypeError(
            f"{label} expected {expected_type}, got {type(value).__name__}."
        )


def _resolve_stop_value(*, expression: str, previous_result: Any, context: dict[str, Any]) -> Any:
    if expression in context:
        return context[expression]
    if isinstance(previous_result, dict) and expression in previous_result:
        return previous_result[expression]
    if isinstance(previous_result, AgentQueryCompleted) and expression == "message":
        return previous_result.message
    return _parse_scalar(expression)

