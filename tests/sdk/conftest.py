import os

import pytest


OPENAI_MODEL = "gpt-5.4-mini"
ANTHROPIC_MODEL = "claude-haiku-4-5"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agnos-sdk")
    group.addoption(
        "--openai",
        action="store_true",
        default=False,
        help=f"Set GLYPH_MODEL to {OPENAI_MODEL} for SDK tests.",
    )
    group.addoption(
        "--anthropic",
        action="store_true",
        default=False,
        help=f"Set GLYPH_MODEL to {ANTHROPIC_MODEL} for SDK tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    use_openai = config.getoption("openai")
    use_anthropic = config.getoption("anthropic")

    if use_openai and use_anthropic:
        raise pytest.UsageError("Use only one of --openai or --anthropic.")

    if use_openai:
        os.environ["GLYPH_MODEL"] = OPENAI_MODEL
    elif use_anthropic:
        os.environ["GLYPH_MODEL"] = ANTHROPIC_MODEL
