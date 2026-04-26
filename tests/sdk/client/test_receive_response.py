import os

import pytest

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import AgentText
from glyph import GlyphClient


@pytest.mark.asyncio
async def test_query_then_receive_response() -> None:
    options = AgentOptions(model=os.environ.get("GLYPH_MODEL"))
    events = []

    async with GlyphClient(options) as client:
        await client.query("Reply with exactly 'I saw your prompt'.")
        async for event in client.receive_response():
            events.append(event)

    assert events
    agent_text_event = next((event for event in events if type(event) == AgentText), None)
    assert agent_text_event.text == "I saw your prompt"

    query_completed = events[-1]
    assert type(query_completed) == AgentQueryCompleted
    assert query_completed.message == "I saw your prompt"
    assert query_completed.stop_reason == "completed" or query_completed.stop_reason == "end_turn"
    assert query_completed.total_cost_usd >= 0
