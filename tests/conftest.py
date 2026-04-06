import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _set_default_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow cassette replay without a real key in env."""
    monkeypatch.setenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "test-openai-key"))


@pytest.fixture(scope="session")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(Path(request.config.rootpath) / "tests" / "cassettes")


@pytest.fixture(scope="session")
def vcr_config() -> dict[str, object]:
    return {
        "decode_compressed_response": True,
        "filter_headers": [
            ("authorization", "DUMMY_AUTH"),
            ("x-api-key", "DUMMY_API_KEY"),
        ],
        "filter_query_parameters": [("api_key", "DUMMY_API_KEY")],
    }
