import pytest

from glyph import AgentOptions
from glyph import resolve_backend


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-4.1-mini", "openai"),
        ("o4-mini", "openai"),
        ("claude-haiku-4-5", "claude"),
    ],
)
def test_resolve_backend(model: str, expected: str) -> None:
    assert resolve_backend(AgentOptions(model=model)) == expected


def test_resolve_backend_unknown_model() -> None:
    with pytest.raises(ValueError, match="Cannot infer backend"):
        resolve_backend(AgentOptions(model="unknown-model-xyz"))
