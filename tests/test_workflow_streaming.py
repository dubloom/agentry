import pytest

import glyph.workflows as workflows_module
import glyph.workflows.decorators as decorators_module
from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import AgentText
from glyph import GlyphWorkflow
from glyph import step


class _FakeStreamingClient:
    def __init__(self, options: AgentOptions) -> None:
        self.options = options
        self.streamed_calls: list[tuple[str, str]] = []
        self.non_streamed_calls: list[tuple[str, str]] = []

    async def __aenter__(self) -> "_FakeStreamingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def set_model(self, model: str) -> None:
        return None

    async def query_and_receive_response(self, prompt: str, session_id: str = "default") -> list[object]:
        self.non_streamed_calls.append((prompt, session_id))
        return [AgentQueryCompleted(message="non-streamed")]

    async def query_streamed(self, prompt: str, session_id: str = "default"):
        self.streamed_calls.append((prompt, session_id))
        yield AgentText(text="hello ")
        yield AgentText(text="world")
        yield AgentQueryCompleted(message="hello world")


@pytest.mark.asyncio
async def test_streaming_llm_step_uses_query_streamed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeStreamingClient(AgentOptions(model="gpt-4.1-mini"))

    def _make_client(options: AgentOptions) -> _FakeStreamingClient:
        assert options.model == "gpt-4.1-mini"
        return fake_client

    monkeypatch.setattr(workflows_module, "GlyphClient", _make_client)

    seen_events: list[object] = []

    class StreamingWorkflow(GlyphWorkflow):
        options = AgentOptions(model="gpt-4.1-mini")

        @step(prompt="Say hi.", is_streaming=True)
        async def call_llm(self) -> None:
            event = yield
            while not isinstance(event, AgentQueryCompleted):
                seen_events.append(event)
                event = yield
            seen_events.append(event)

    result = await StreamingWorkflow.run(session_id="streaming-session")

    assert fake_client.streamed_calls == [("Say hi.", "streaming-session")]
    assert fake_client.non_streamed_calls == []
    assert [type(event) for event in seen_events] == [AgentText, AgentText, AgentQueryCompleted]
    assert isinstance(result, AgentQueryCompleted)
    assert result.message == "hello world"


@pytest.mark.asyncio
async def test_streaming_llm_step_requires_async_generator() -> None:
    class InvalidStreamingWorkflow(GlyphWorkflow):
        options = AgentOptions(model="gpt-4.1-mini")

        @step(prompt="Say hi.", is_streaming=True)
        async def call_llm(self) -> None:
            return None

    with pytest.raises(TypeError, match="Streaming LLM steps must be async generators"):
        await InvalidStreamingWorkflow.run(session_id="streaming-session")


def test_streaming_python_step_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING", logger=decorators_module.__name__)

    class InvalidStreamingPythonWorkflow(GlyphWorkflow):
        @step(is_streaming=True)
        async def first(self) -> None:
            return None

    assert InvalidStreamingPythonWorkflow._glyph_step_descriptors[0].kind == "python"
    assert "ignoring it for python step `first`" in caplog.text
