"""Workflow step decorator and descriptor types."""
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Literal
from typing import TypeVar
from typing import overload


StepKind = Literal["python", "llm"]
F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True)
class StepDescriptor:
    func: Callable[..., Any]
    kind: StepKind
    prompt: str | None
    model: str | None


@overload
def step(func: F, /) -> F:
    ...


@overload
def step(
    *,
    prompt: str | None = None,
    model: str | None = None,
) -> Callable[[F], F]:
    ...


def step(
    func: F | None = None,
    /,
    *,
    prompt: str | None = None,
    model: str | None = None,
) -> F | Callable[[F], F]:
    """Mark a workflow method as a step.

    - ``@step`` defines a plain Python step.
    - ``@step(prompt=..., model=...)`` defines an LLM step.
    """

    def _decorate(candidate: F) -> F:
        kind: StepKind = "llm" if prompt is not None or model is not None else "python"
        setattr(
            candidate,
            "_glyph_step",
            StepDescriptor(
                func=candidate,
                kind=kind,
                prompt=prompt,
                model=model,
            ),
        )
        return candidate

    if func is not None:
        return _decorate(func)

    return _decorate


__all__ = ["StepDescriptor", "step"]